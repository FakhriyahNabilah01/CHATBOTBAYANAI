import os, re, json
from typing import List, Dict, Any, Optional

from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from typing import Set


load_dotenv()

def get_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY belum diset. Cek file .env")

    llm = ChatOpenAI(
        model="gpt-4o",
        api_key=api_key,
        temperature=0,
    )
    return llm

def get_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", "Kamu asisten yang menjawab berdasarkan konteks ayat/tafsir yang diberikan. Jangan mengarang di luar konteks."),
        ("human", "Pertanyaan:\n{question}\n\nKonteks:\n{context}\n\nJawab singkat, jelas, dan sertakan rujukan surat:ayat dari konteks."),
    ])

planner_prompt = ChatPromptTemplate.from_messages([
    ("system",
     """Kamu adalah PLANNER untuk chatbot tafsir Qur'an berbasis GraphRAG (Neo4j).

TUGAS UTAMA:
- Mengubah input user menjadi rencana dalam format JSON **valid saja**.
- Planner TIDAK menjawab isi tafsir, TIDAK menambah data, TIDAK menebak ayat.

KETERBATASAN DATASET (WAJIB):
- Dataset HANYA berisi ayat-ayat TERPILIH dari Juz 30 (surat pendek Makkiyah/Madaniyah akhir).
- JANGAN pernah merencanakan pencarian surat/ayat di luar dataset ini.
- Jika user minta sesuatu di luar dataset → intent = "clarify".

ATURAN INTENT (pilih SATU saja):
- "search": query baru tentang topik (hisab, kiamat, tamak, dll.)
- "more": user minta lanjutan hasil sebelumnya ("5 lagi", "lanjut", "berikan lagi")
- "detail": user minta penjelasan ayat spesifik dari hasil sebelumnya ("jelaskan ayat 15", "tafsir ayat 20")
- "clarify": ambigu, minta data di luar dataset, atau butuh konfirmasi ("surat Al-Baqarah", "10 surat lain")

FIELD JSON WAJIB:
{
  "intent": "search" | "more" | "detail" | "clarify",
  "query": "topik ringkas untuk pencarian" (wajib),
  "k": integer (jumlah ayat yang diminta, default 5 jika tidak jelas),
  "source": "all" | "hamka" | "kemenag_tahlili" | "kemenag_wajiz" (default "all" jika tidak disebut),
  "ayat_number": integer atau null (hanya untuk intent="detail"),
  "clarify_message": string atau null (jika intent="clarify")
}

CONTOH OUTPUT (hanya JSON, tanpa teks lain):
{"intent": "search", "query": "hari hisab", "k": 5, "source": "all", "ayat_number": null, "clarify_message": null}

JANGAN tambah penjelasan di luar JSON."""),
    ("human", "User input: {user_text}")
])

def build_planner_chain():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY belum diset (cek .env).")

    llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=api_key)
    return planner_prompt | llm | StrOutputParser()


def safe_parse_plan(text: str) -> Dict[str, Any]:
    text = (text or "").strip()

    # coba parse langsung
    try:
        plan = json.loads(text)
        return plan if isinstance(plan, dict) else {}
    except Exception:
        pass

    # coba cari blok JSON
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            plan = json.loads(m.group(0))
            return plan if isinstance(plan, dict) else {}
        except Exception:
            return {}

    return {}


# optional: biar kompatibel sama pemanggilan lama
def parse_plan(plan_text: str) -> Dict[str, Any]:
    return safe_parse_plan(plan_text)

examples = [

    # =========================
    # 1. Query umum / topik
    # =========================
    {
        "user": "gambaran hisab",
        "assistant":
        "Baik. Saya akan mencari ayat-ayat yang membahas Hari Hisab (Yaum al-Ḥisāb), "
        "lalu menyajikannya berdasarkan CONTEXT yang tersedia, mencakup ayat Arab, "
        "terjemahan, kategori, serta tafsir yang ada."
    },

    {
        "user": "apa yang terjadi pada hari kiamat?",
        "assistant":
        "Baik. Saya akan menyajikan penjelasan tentang peristiwa Hari Kiamat "
        "berdasarkan ayat-ayat yang relevan di CONTEXT, dilengkapi dengan "
        "terjemahan, kategori, dan tafsir yang tersedia."
    },

    # =========================
    # 2. Filter tafsir spesifik
    # =========================
    {
        "user": "tafsir buya hamka tentang tamak",
        "assistant":
        "Baik. Saya akan fokus menampilkan Tafsir Buya Hamka saja yang relevan "
        "dengan tema tamak atau kerakusan, berdasarkan data yang tersedia di CONTEXT."
    },

    {
        "user": "tolong kemenag wajiz aja tentang hari pembalasan",
        "assistant":
        "Siap. Saya akan menyajikan ayat yang membahas Hari Pembalasan "
        "berdasarkan CONTEXT, dengan menampilkan terjemahan, kategori, dan "
        "Tafsir Kemenag (Wajiz) saja."
    },

    {
        "user": "kemenag tahlili tentang amal manusia",
        "assistant":
        "Baik. Saya akan menampilkan penjelasan dari Tafsir Kemenag (Tahlili) "
        "yang membahas amal perbuatan manusia, berdasarkan ayat-ayat yang tersedia di CONTEXT."
    },

    # =========================
    # 3. Istilah ambigu
    # =========================
    {
        "user": "hari penentuan itu gimana?",
        "assistant":
        "Baik. Istilah 'hari penentuan' biasanya merujuk pada Hari Pemutusan Perkara. "
        "Saya akan mencari ayat yang relevan dan menyajikannya berdasarkan CONTEXT "
        "beserta tafsir yang tersedia."
    },

    {
        "user": "tutup buku amal manusia",
        "assistant":
        "Baik. Ungkapan tersebut biasanya berkaitan dengan perhitungan amal. "
        "Saya akan menyajikan ayat-ayat yang relevan berdasarkan CONTEXT "
        "beserta terjemahan dan tafsir yang tersedia."
    },

    # =========================
    # 4. Pagination / lanjutan
    # =========================
    {
        "user": "berikan 5 lagi",
        "assistant":
        "Baik. Saya akan menampilkan tambahan hasil dari pencarian sebelumnya, "
        "selama data tersebut tersedia di dalam CONTEXT."
    },

    {
        "user": "lanjutkan",
        "assistant":
        "Baik. Saya akan melanjutkan pembahasan berdasarkan hasil sebelumnya "
        "tanpa mengubah topik, sesuai data yang tersedia."
    },

    # =========================
    # 5. Pertanyaan kompleks
    # =========================
    {
        "user": "perbuatan apa yang membuat manusia masuk surga?",
        "assistant":
        "Baik. Saya akan menyajikan ayat-ayat yang menjelaskan perbuatan "
        "yang menjadi sebab masuk surga berdasarkan CONTEXT, "
        "dilengkapi dengan terjemahan, kategori, dan tafsir yang tersedia."
    },

    # =========================
    # 6. Penolakan aman (ANTI HALUSINASI)
    # =========================
    {
        "user": "sebutkan 10 surat lain di luar yang ada",
        "assistant":
        "Maaf, permintaan tersebut tidak dapat dipenuhi karena data tersebut "
        "tidak tersedia di dalam dataset yang digunakan."
    },

    {
        "user": "tambahkan ayat dari surat lain",
        "assistant":
        "Maaf, saya hanya dapat menyajikan ayat dan tafsir yang tersedia "
        "di dalam CONTEXT sesuai dengan dataset."
    },

    # UBahan/Baru: Tambah buat handle new/followup lebih baik
    {
        "user": "jelaskan topik baru setelah yang lama",
        "assistant":
        "Baik. Ini topik baru, saya akan fokus ke konteks baru berdasarkan CONTEXT, tanpa campur yang sebelumnya."
    },
    {
        "user": "lanjutkan dari sebelumnya",
        "assistant":
        "Baik. Melanjutkan dari konteks sebelumnya berdasarkan CONTEXT."
    },

    {
        "user": "gambaran hisab",
        "assistant": "Baik. Saya akan mencari ayat-ayat yang membahas Hari Hisab (Yaum al-Ḥisāb), lalu menyajikannya berdasarkan CONTEXT yang tersedia, mencakup ayat Arab, terjemahan, kategori, serta tafsir yang ada."
    },
    {
        "user": "apa yang terjadi pada hari kiamat?",
        "assistant": "Baik. Saya akan menyajikan penjelasan tentang peristiwa Hari Kiamat berdasarkan ayat-ayat yang relevan di CONTEXT, dilengkapi dengan terjemahan, kategori, dan tafsir yang tersedia."
    },
    {
        "user": "tafsir buya hamka tentang tamak",
        "assistant": "Baik. Saya akan fokus menampilkan Tafsir Buya Hamka saja yang relevan dengan tema tamak atau kerakusan, berdasarkan data yang tersedia di CONTEXT."
    },
    {
        "user": "tolong kemenag wajiz aja tentang hari pembalasan",
        "assistant": "Siap. Saya akan menyajikan ayat yang membahas Hari Pembalasan berdasarkan CONTEXT, dengan menampilkan terjemahan, kategori, dan Tafsir Kemenag (Wajiz) saja."
    },
    {
        "user": "kemenag tahlili tentang amal manusia",
        "assistant": "Baik. Saya akan menampilkan penjelasan dari Tafsir Kemenag (Tahlili) yang membahas amal perbuatan manusia, berdasarkan ayat-ayat yang tersedia di CONTEXT."
    },
    {
        "user": "hari penentuan itu gimana?",
        "assistant": "Baik. Istilah 'hari penentuan' biasanya merujuk pada Hari Pemutusan Perkara. Saya akan mencari ayat yang relevan dan menyajikannya berdasarkan CONTEXT beserta tafsir yang tersedia."
    },
    {
        "user": "tutup buku amal manusia",
        "assistant": "Baik. Ungkapan tersebut biasanya berkaitan dengan perhitungan amal. Saya akan menyajikan ayat-ayat yang relevan berdasarkan CONTEXT beserta terjemahan dan tafsir yang tersedia."
    },
    {
        "user": "berikan 5 lagi",
        "assistant": "Baik. Saya akan menampilkan tambahan hasil dari pencarian sebelumnya, selama data tersebut tersedia di dalam CONTEXT."
    },
    {
        "user": "lanjutkan",
        "assistant": "Baik. Saya akan melanjutkan pembahasan berdasarkan hasil sebelumnya tanpa mengubah topik, sesuai data yang tersedia."
    },
    {
        "user": "perbuatan apa yang membuat manusia masuk surga?",
        "assistant": "Baik. Saya akan menyajikan ayat-ayat yang menjelaskan perbuatan yang menjadi sebab masuk surga berdasarkan CONTEXT, dilengkapi dengan terjemahan, kategori, dan tafsir yang tersedia."
    },
    {
        "user": "sebutkan 10 surat lain di luar yang ada",
        "assistant": "Maaf, permintaan tersebut tidak dapat dipenuhi karena data tersebut tidak tersedia di dalam dataset yang digunakan."
    },
    {
        "user": "tambahkan ayat dari surat lain",
        "assistant": "Maaf, saya hanya dapat menyajikan ayat dan tafsir yang tersedia di dalam CONTEXT sesuai dengan dataset."
    },
    {
        "user": "jelaskan topik baru setelah yang lama",
        "assistant": "Baik. Ini topik baru, saya akan fokus ke konteks baru berdasarkan CONTEXT, tanpa campur yang sebelumnya."
    },
    {
        "user": "lanjutkan dari sebelumnya",
        "assistant": "Baik. Melanjutkan dari konteks sebelumnya berdasarkan CONTEXT."
    },

    # =========================
    # 1. Query umum / topik
    # =========================
    {
        "user": "gambaran hisab",
        "assistant":
        "Baik. Saya akan mencari ayat-ayat yang membahas Hari Hisab (Yaum al-Ḥisāb), "
        "lalu menyajikannya berdasarkan CONTEXT yang tersedia, mencakup ayat Arab, "
        "terjemahan, kategori, serta tafsir yang ada."
    },

    {
        "user": "apa yang terjadi pada hari kiamat?",
        "assistant":
        "Baik. Saya akan menyajikan penjelasan tentang peristiwa Hari Kiamat "
        "berdasarkan ayat-ayat yang relevan di CONTEXT, dilengkapi dengan "
        "terjemahan, kategori, dan tafsir yang tersedia."
    },

    # =========================
    # 2. Filter tafsir spesifik
    # =========================
    {
        "user": "tafsir buya hamka tentang tamak",
        "assistant":
        "Baik. Saya akan fokus menampilkan Tafsir Buya Hamka saja yang relevan "
        "dengan tema tamak atau kerakusan, berdasarkan data yang tersedia di CONTEXT."
    },

    {
        "user": "tolong kemenag wajiz aja tentang hari pembalasan",
        "assistant":
        "Siap. Saya akan menyajikan ayat yang membahas Hari Pembalasan "
        "berdasarkan CONTEXT, dengan menampilkan terjemahan, kategori, dan "
        "Tafsir Kemenag (Wajiz) saja."
    },

    {
        "user": "kemenag tahlili tentang amal manusia",
        "assistant":
        "Baik. Saya akan menampilkan penjelasan dari Tafsir Kemenag (Tahlili) "
        "yang membahas amal perbuatan manusia, berdasarkan ayat-ayat yang tersedia di CONTEXT."
    },

    # =========================
    # 3. Istilah ambigu
    # =========================
    {
        "user": "hari penentuan itu gimana?",
        "assistant":
        "Baik. Istilah 'hari penentuan' biasanya merujuk pada Hari Pemutusan Perkara. "
        "Saya akan mencari ayat yang relevan dan menyajikannya berdasarkan CONTEXT "
        "beserta tafsir yang tersedia."
    },

    {
        "user": "tutup buku amal manusia",
        "assistant":
        "Baik. Ungkapan tersebut biasanya berkaitan dengan perhitungan amal. "
        "Saya akan menyajikan ayat-ayat yang relevan berdasarkan CONTEXT "
        "beserta terjemahan dan tafsir yang tersedia."
    },

    # =========================
    # 4. Pagination / lanjutan
    # =========================
    {
        "user": "berikan 5 lagi",
        "assistant":
        "Baik. Saya akan menampilkan tambahan hasil dari pencarian sebelumnya, "
        "selama data tersebut tersedia di dalam CONTEXT."
    },

    {
        "user": "lanjutkan",
        "assistant":
        "Baik. Saya akan melanjutkan pembahasan berdasarkan hasil sebelumnya "
        "tanpa mengubah topik, sesuai data yang tersedia."
    },

    # =========================
    # 5. Pertanyaan kompleks
    # =========================
    {
        "user": "perbuatan apa yang membuat manusia masuk surga?",
        "assistant":
        "Baik. Saya akan menyajikan ayat-ayat yang menjelaskan perbuatan "
        "yang menjadi sebab masuk surga berdasarkan CONTEXT, "
        "dilengkapi dengan terjemahan, kategori, dan tafsir yang tersedia."
    },

    # =========================
    # 6. Penolakan aman (ANTI HALUSINASI)
    # =========================
    {
        "user": "sebutkan 10 surat lain di luar yang ada",
        "assistant":
        "Maaf, permintaan tersebut tidak dapat dipenuhi karena data tersebut "
        "tidak tersedia di dalam dataset yang digunakan."
    },

    {
        "user": "tambahkan ayat dari surat lain",
        "assistant":
        "Maaf, saya hanya dapat menyajikan ayat dan tafsir yang tersedia "
        "di dalam CONTEXT sesuai dengan dataset."
    },

    # UBahan/Baru: Tambah buat handle new/followup lebih baik
    {
        "user": "jelaskan topik baru setelah yang lama",
        "assistant":
        "Baik. Ini topik baru, saya akan fokus ke konteks baru berdasarkan CONTEXT, tanpa campur yang sebelumnya."
    },
    {
        "user": "lanjutkan dari sebelumnya",
        "assistant":
        "Baik. Melanjutkan dari konteks sebelumnya berdasarkan CONTEXT."
    },
]

fewshot = FewShotChatMessagePromptTemplate(
    examples=examples,
    input_variables=["user_text"],
    example_prompt=ChatPromptTemplate.from_messages([
        ("human", "{user}"),
        ("ai", "{assistant}")
    ])
)

qa_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Kamu adalah asisten tafsir Al-Qur'an berbasis GraphRAG (Neo4j).\n\n"

     "ATURAN KERAS (WAJIB DIPATUHI):\n"
     "- Jawaban HANYA BOLEH menggunakan informasi dari CONTEXT.\n"
     "- DILARANG menambah ayat, tafsir, contoh, atau pengetahuan di luar CONTEXT.\n"
     "- DILARANG menyebut surat atau ayat yang TIDAK ADA di CONTEXT.\n"
     "- DILARANG menambah jumlah ayat melebihi yang tersedia di CONTEXT.\n"
     "- Kamu BUKAN mesin pencari dan BUKAN pengetahuan umum.\n\n"

     "ATURAN REFERENSI:\n"
     "- Setiap penjelasan HARUS menyebutkan surat dan ayat yang dirujuk.\n"
     "- Jika tidak ada rujukan eksplisit dalam CONTEXT, jawab:\n"
     "  'Tidak ditemukan rujukan eksplisit dalam konteks.'\n\n"

     "ATURAN FILTER:\n"
     "- Jika user meminta 'hamka saja' → tampilkan hanya tafsir_buya_hamka.\n"
     "- Jika user meminta 'kemenag wajiz' → tampilkan hanya tafsir_kemenag_wajiz.\n"
     "- Jika user meminta 'kemenag tahlili' → tampilkan hanya tafsir_kemenag_tahlili.\n"
     "- Jika tidak disebutkan, tampilkan semua tafsir yang tersedia di CONTEXT.\n\n"

     "FORMAT JAWABAN:\n"
     "- Jawaban rapi, terstruktur, dan faktual.\n"
     "- Tanpa asumsi tambahan.\n\n"

     "Jika konteks tidak cukup untuk menjawab pertanyaan user, jawab:\n"
     "'Konteks tidak mencukupi.'"
    ),

    fewshot,
    MessagesPlaceholder("history"),

    ("human",
     "USER:\n{user_text}\n\n"
     "CONTEXT:\n{context}\n\n"
     "Jawab sesuai ATURAN di atas."
    )
])

#answer_chain = qa_prompt | llm | StrOutputParser()
def build_answer_chain():
    llm = get_llm()
    return qa_prompt | llm | StrOutputParser()

# === KESIMPULAN ===
def generate_contextual_conclusion(topic: str, records: List[Dict], sources: Set[str], is_final: bool = False) -> str:
    if not records:
        return "Belum ada data untuk kesimpulan."

    chunks = []
    max_records = min(30 if is_final else 15, len(records))
    for r in records[:max_records]:
        for key in ["tafsir_tahlili", "tafsir_wajiz", "tafsir_hamka"]:
            if ("all" in sources or key.split("_")[-1] in sources) and (txt := r.get(key)):
                chunks.append(txt)

    if not chunks:
        return "Tidak cukup data tafsir untuk kesimpulan."

    prompt_type = "kesimpulan akhir (lebih mendalam, komprehensif, dan merangkum seluruh aspek)" if is_final else "kesimpulan sementara"
    prompt = f"""
    Berdasarkan ayat-ayat dan tafsir berikut tentang "{topic}":
    {chr(10).join("- " + c for c in chunks)}

    Buat {prompt_type} yang panjang dan mendalam (6-10 kalimat), tetap objektif, akademis, dan berbasis isi ayat serta tafsir yang ada.
    - Jelaskan makna utama dan kaitannya dengan perilaku manusia di dunia.
    - Ringkas semua elemen penting dari seluruh batch.
    - Gunakan bahasa formal, jelas.
    - Jangan tambah opini pribadi, tetap setia pada teks Al-Qur'an dan tafsir yang disediakan.
    """

    try:
        llm = get_llm()
        response = llm.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        print(f"[ERROR] Kesimpulan gagal: {e}")
        return "Kesimpulan gagal dibuat karena error teknis."