import os
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD)
)


def run_cypher(query: str, **params) -> List[Dict[str, Any]]:
    """Helper umum untuk menjalankan cypher dan mengembalikan list of dict."""
    with driver.session() as session:
        rs = session.run(query, **params)
        return [r.data() for r in rs]


def get_ayat(nama_surat: str, ayat_ke: int) -> Optional[Dict[str, Any]]:
    """
    Ambil 1 ayat lengkap (arab + terjemahan + kategori + tafsir).
    Return keys KONSISTEN:
      nama_surat, ayat_ke, arab_ayat, terjemahan, kategori, tafsir_tahlili, tafsir_wajiz, tafsir_hamka
    """
    query = """
    MATCH (s:Surat)-[:beradadi|terdapat]-(a:Ayat)
    WHERE
      (
        toUpper(s.Surat) = toUpper($surat)
        OR toUpper(replace(s.Surat, "'", "")) = toUpper(replace($surat, "'", ""))
        OR toUpper(s.Surat) CONTAINS toUpper($surat)
        OR toUpper(replace(s.Surat, "'", "")) CONTAINS toUpper(replace($surat, "'", ""))
      )
      AND toInteger(a.AyatKe) = toInteger($ayat_ke)

    OPTIONAL MATCH (a)-[:memiliki_arti|untuk]-(tr:Terjemahan)
    OPTIONAL MATCH (a)-[:memiliki|terdapat]-(bh:TafsirBuyaHamka)
    OPTIONAL MATCH (a)-[:memiliki|terdapat]-(th:TafsirKemenagTahlili)
    OPTIONAL MATCH (a)-[:memiliki|terdapat]-(wz:TafsirKemenagWajiz)
    OPTIONAL MATCH (a)-[:masuk_ke|pada]-(k:Kategori)

    WITH
      s, a,
      head(collect(DISTINCT tr.Terjemahan)) AS terjemahan,
      collect(DISTINCT k.Kategori) AS kategori,
      collect(DISTINCT bh.TafsirBuyaHamka) AS hamka_parts,
      collect(DISTINCT th.TafsirKemenagTahlili) AS tahlili_parts,
      collect(DISTINCT wz.TafsirKemenagWajiz) AS wajiz_parts

    RETURN
      s.Surat AS nama_surat,
      toInteger(a.AyatKe) AS ayat_ke,
      a.Ayat AS arab_ayat,
      terjemahan AS terjemahan,

      reduce(out = "", x IN [p IN hamka_parts   WHERE p IS NOT NULL AND trim(p) <> "" | p]
             | out + CASE WHEN out = "" THEN "" ELSE "\\n\\n" END + x) AS tafsir_hamka,

      reduce(out = "", x IN [p IN tahlili_parts WHERE p IS NOT NULL AND trim(p) <> "" | p]
             | out + CASE WHEN out = "" THEN "" ELSE "\\n\\n" END + x) AS tafsir_tahlili,

      reduce(out = "", x IN [p IN wajiz_parts   WHERE p IS NOT NULL AND trim(p) <> "" | p]
             | out + CASE WHEN out = "" THEN "" ELSE "\\n\\n" END + x) AS tafsir_wajiz,

      [x IN kategori WHERE x IS NOT NULL AND trim(x) <> ""] AS kategori
    LIMIT 1
    """

    with driver.session() as session:
        rec = session.run(query, surat=nama_surat, ayat_ke=ayat_ke).single()
        return rec.data() if rec else None


def graphrag_search(query_embedding, limit: int = 10, score_threshold: float = 0.7) -> List[Dict[str, Any]]:
    """
    Vector search (GraphRAG).
    Return keys KONSISTEN:
      nama_surat, ayat_ke, arab_ayat, terjemahan, kategori, tafsir_tahlili, tafsir_wajiz, tafsir_hamka, score
    """
    query = """
    CALL db.index.vector.queryNodes(
        'terjemahan_vector_index',
        $limit,
        $vector
    ) YIELD node AS t, score

    WHERE score >= $threshold

    MATCH (t)-[:untuk|memiliki_arti]-(a:Ayat)-[:beradadi|terdapat]-(s:Surat)
    OPTIONAL MATCH (a)-[:memiliki_arti|untuk]-(tr:Terjemahan)
    OPTIONAL MATCH (a)-[:pada|masuk_ke]-(k:Kategori)
    OPTIONAL MATCH (a)-[:terdapat|memiliki]-(th:TafsirKemenagTahlili)
    OPTIONAL MATCH (a)-[:terdapat|memiliki]-(wz:TafsirKemenagWajiz)
    OPTIONAL MATCH (a)-[:terdapat|memiliki]-(bh:TafsirBuyaHamka)

    WITH
      s.Surat AS nama_surat,
      toInteger(a.AyatKe) AS ayat_ke,
      a.Ayat AS arab_ayat,
      coalesce(t.Terjemahan, tr.Terjemahan) AS terjemahan,
      collect(DISTINCT k.Kategori) AS kategori,
      head(collect(DISTINCT th.TafsirKemenagTahlili)) AS tafsir_tahlili,
      head(collect(DISTINCT wz.TafsirKemenagWajiz)) AS tafsir_wajiz,
      head(collect(DISTINCT bh.TafsirBuyaHamka)) AS tafsir_hamka,
      score AS score

    RETURN
      nama_surat,
      ayat_ke,
      arab_ayat,
      terjemahan,
      [x IN kategori WHERE x IS NOT NULL AND trim(x) <> ""] AS kategori,
      tafsir_tahlili,
      tafsir_wajiz,
      tafsir_hamka,
      score
    ORDER BY score DESC
    LIMIT $limit
    """

    with driver.session() as session:
        rs = session.run(
            query,
            vector=query_embedding,
            limit=limit,
            threshold=score_threshold
        )
        return [r.data() for r in rs]
