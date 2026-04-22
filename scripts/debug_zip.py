"""zip 파일 내부 구조 및 JSON 내용 진단 - 결과를 파일로 출력"""
import zipfile
import json
from pathlib import Path

AUDIO_ZIP = r"C:\Users\dns-server2\TTT-Dialect\data\raw\elderly\자유대화 음성(노인남녀)\Training\[원천]1.AI챗봇_1.zip"
LABEL_ZIP = r"F:\TTT-data\raw\elderly\[라벨]1.AI챗봇.zip"
OUTPUT = r"F:\TTT-data\debug_output.txt"

with open(OUTPUT, "w", encoding="utf-8") as out:
    # stem 매칭 확인
    with zipfile.ZipFile(AUDIO_ZIP, "r") as azf:
        wav_stems = {Path(n).stem for n in azf.namelist() if n.lower().endswith(".wav")}
    with zipfile.ZipFile(LABEL_ZIP, "r") as lzf:
        json_stems = {Path(n).stem for n in lzf.namelist() if n.lower().endswith(".json")}
    
    matched = wav_stems & json_stems
    out.write(f"음성 stem: {len(wav_stems)}개\n")
    out.write(f"라벨 stem: {len(json_stems)}개\n")
    out.write(f"매칭: {len(matched)}개\n\n")

    # JSON 내용 샘플
    out.write("=== JSON 내용 샘플 (처음 2개) ===\n")
    with zipfile.ZipFile(LABEL_ZIP, "r") as lzf:
        json_entries = [n for n in lzf.namelist() if n.lower().endswith(".json")]
        for entry in json_entries[:2]:
            try:
                with lzf.open(entry) as f:
                    raw = f.read()
                try:
                    data = json.loads(raw.decode('utf-8'))
                except UnicodeDecodeError:
                    data = json.loads(raw.decode('euc-kr'))
                out.write(json.dumps(data, ensure_ascii=False, indent=2))
                out.write("\n---\n")
            except Exception as e:
                out.write(f"오류: {e}\n")

print(f"결과 저장됨: {OUTPUT}")
