import os
import sys
import numpy as np
import torch

# Ensure we can import modules from webapp/backend
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "webapp", "backend"))
sys.path.append(backend_path)

from services.whisper_asr import WhisperASR

def levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
        
    return previous_row[-1]

def calculate_cer(reference, hypothesis):
    ref_chars = list(reference.replace(" ", ""))
    hyp_chars = list(hypothesis.replace(" ", ""))
    if not ref_chars:
        return 1.0 if hyp_chars else 0.0
    dist = levenshtein_distance(ref_chars, hyp_chars)
    return dist / len(ref_chars)

def evaluate_models(audio_folder, transcript_file):
    # Read transcripts
    transcripts = {}
    if not os.path.exists(transcript_file):
        print(f"Error: Transcript file not found at {transcript_file}")
        return
        
    with open(transcript_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "|" not in line:
                continue
            parts = line.split("|")
            filename = parts[0].strip()
            text = parts[1].strip()
            transcripts[filename] = text

    if not transcripts:
        print("No transcripts found in the file.")
        return

    models = {
        "best1 (elderly_command)": "best1",
        "best2 (gangwon)": "best2/best",
        "best3 (combined)": "best3/best"
    }

    # Verify audio files exist
    audio_paths = {}
    for filename in transcripts.keys():
        path = os.path.join(audio_folder, filename)
        if os.path.exists(path):
            audio_paths[filename] = path
        else:
            print(f"Warning: Audio file not found: {path}")

    if not audio_paths:
        print("No matching audio files found on disk.")
        return

    print(f"\nLoaded {len(audio_paths)} test samples.")
    results = {name: [] for name in models.keys()}

    for model_name, model_path in models.items():
        print(f"\n--- Evaluating {model_name} ---")
        try:
            # Initialize ASR
            asr = WhisperASR(model_path=model_path)
            
            import librosa
            
            total_cer = 0.0
            count = 0
            
            for filename, path in audio_paths.items():
                ref_text = transcripts[filename]
                
                # Load audio
                audio, sr = librosa.load(path, sr=16000)
                
                # Transcribe
                pred_text = asr.transcribe(audio, sr=16000)
                
                cer = calculate_cer(ref_text, pred_text)
                total_cer += cer
                count += 1
                
                print(f"[{filename}]")
                print(f"  Ref : {ref_text}")
                print(f"  Pred: {pred_text}")
                print(f"  CER : {cer:.4f}")
                
            avg_cer = total_cer / count if count > 0 else 0.0
            print(f"\n=> Average CER for {model_name}: {avg_cer:.4f}")
            
        except Exception as e:
            print(f"Failed to evaluate {model_name}: {e}")

if __name__ == "__main__":
    # Example usage: python evaluate_asr.py <audio_folder> <transcript_file>
    if len(sys.argv) < 3:
        print("Usage: python evaluate_asr.py <audio_folder> <transcript_file>")
        print("\nTranscript file format:")
        print("file1.wav | 정답 텍스트")
        print("file2.wav | 또 다른 정답")
        sys.exit(1)
        
    evaluate_models(sys.argv[1], sys.argv[2])
