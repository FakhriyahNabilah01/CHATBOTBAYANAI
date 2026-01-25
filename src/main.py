# src/main.py
from controller import controller

def main():
    session_id = "default"

    while True:
        user_text = input("Ketik pertanyaan kamu (atau 'exit'): ").strip()
        if not user_text:
            continue
        if user_text.lower() in ("exit", "quit"):
            break

        result = controller(user_text, session_id=session_id)
        # INI YANG BIKIN OUTPUT PASTI KELUAR
        print(result)

if __name__ == "__main__":
    main()
