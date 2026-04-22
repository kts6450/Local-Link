"""zip 파일 내부 구조 및 stem 매칭 진단"""
import zipfile
from pathlib import Path

AUDIO_ZIP = r"C:\Users\dns-server2\TTT-Dialect\data\raw\elderly\자유대화 음성(노인남녀)\Training\[원천]1.AI챗봇_1.zip"
LABEL_ZIP = r"F:\TTT-data\raw\elderly\[라벨]1.AI챗봇.zip"

print("=== 원천 ZIP (음성) 첫 5개 항목 ===")
with zipfile.ZipFile(AUDIO_ZIP, "r") as zf:
    entries = zf.namelist()
    wav_entries = [n for n in entries if n.lower().endswith(".wav")]
    print(f"전체 항목: {len(entries)}개, wav: {len(wav_entries)}개")
    for e in wav_entries[:5]:
        stem = Path(e).stem
        print(f"  항목: {repr(e)}")
        print(f"  stem: {repr(stem)}")

print()
print("=== 라벨 ZIP (JSON) 첫 5개 항목 ===")
with zipfile.ZipFile(LABEL_ZIP, "r") as zf:
    entries = zf.namelist()
    json_entries = [n for n in entries if n.lower().endswith(".json")]
    print(f"전체 항목: {len(entries)}개, json: {len(json_entries)}개")
    for e in json_entries[:5]:
        stem = Path(e).stem
        print(f"  항목: {repr(e)}")
        print(f"  stem: {repr(stem)}")

print()
print("=== stem 매칭 테스트 ===")
with zipfile.ZipFile(AUDIO_ZIP, "r") as azf:
    wav_stems = {Path(n).stem for n in azf.namelist() if n.lower().endswith(".wav")}

with zipfile.ZipFile(LABEL_ZIP, "r") as lzf:
    json_stems = {Path(n).stem for n in lzf.namelist() if n.lower().endswith(".json")}

matched = wav_stems & json_stems
print(f"음성 stem: {len(wav_stems)}개")
print(f"라벨 stem: {len(json_stems)}개")
print(f"매칭: {len(matched)}개")

print(f"\n=== JSON 내용 샘플 확인 ===")
with zipfile.ZipFile(LABEL_ZIP, "r") as lzf:
    json_entries = [n for n in lzf.namelist() if n.lower().endswith(".json")]
    for entry in json_entries[:3]:
        print(f"\n파일: {Path(entry).name}")
        try:
            with lzf.open(entry) as f:
                raw = f.read()
            # UTF-8 시도
            try:
                data = __import__('json').loads(raw.decode('utf-8'))
                print(f"  인코딩: UTF-8")
            except UnicodeDecodeError:
                data = __import__('json').loads(raw.decode('euc-kr'))
                print(f"  인코딩: EUC-KR")
            
            print(f"  최상위 키: {list(data.keys())}")
            for key in data.keys():
                print(f"  [{key}]: {data[key]}")
        except Exception as e:
            print(f"  오류: {e}")
