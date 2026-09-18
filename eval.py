import os
import json
import math
import hashlib
import argparse
from pathlib import Path

import requests
import pandas as pd
from tqdm import tqdm

# Replace with your actual OpenAI API key
api_key = os.environ.get('OPENAI_API_KEY', 'YOUR_API_KEY')

def parse_args():
    """
    Parse command-line arguments for prediction file and test file paths.
    """
    parser = argparse.ArgumentParser(description="Evaluate question-answer predictions using GPT-4o-mini")
    parser.add_argument("--pred_path", type=str, required=True, help="Path to the prediction .jsonl file")
    parser.add_argument("--test_path", type=str, required=True, help="Path to the test set .csv file")
    return parser.parse_args()


def load_predictions(pred_path):
    """Load prediction records from a JSONL file."""
    predictions = []
    with open(pred_path, encoding='utf-8') as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc.msg}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"Prediction on line {line_number} must be a JSON object")
            if 'question_id' not in item or 'pred' not in item:
                raise ValueError(f"Prediction on line {line_number} requires question_id and pred")
            predictions.append(item)
    return predictions


def normalize_score(value):
    """Convert an external score to the supported 0-to-5 range."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(score):
        return 0.0
    return min(max(score, 0.0), 5.0)


def result_filename(question_id):
    """Return a filesystem-safe cache filename for a question ID."""
    digest = hashlib.sha256(str(question_id).encode('utf-8')).hexdigest()[:24]
    return f"score_{digest}.json"


def cache_matches(result_path, qa_set):
    """Check whether a cached score was produced for the current QA input."""
    path = Path(result_path)
    if not path.exists():
        return False
    try:
        cached = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(cached, list)
        and len(cached) == 2
        and isinstance(cached[0], dict)
        and cached[1] == qa_set
    )


def collect_results(output_dir, prediction_set):
    """Collect only cache entries that belong to the current evaluation run."""
    combined_results = {}
    output_dir = Path(output_dir)
    for question_id, qa_set in prediction_set.items():
        result_path = output_dir / result_filename(question_id)
        if not cache_matches(result_path, qa_set):
            raise ValueError(f"Missing or stale score cache for question ID: {question_id}")
        combined_results[question_id] = json.loads(result_path.read_text(encoding='utf-8'))
    return combined_results


def parse_score_response(content):
    """Parse and normalize the JSON object returned by the scoring model."""
    content = content.strip()
    if content.startswith('```'):
        lines = content.splitlines()
        content = '\n'.join(lines[1:-1]).strip()
    result = json.loads(content)
    if not isinstance(result, dict):
        raise ValueError("Scoring response must be a JSON object")
    prediction = str(result.get('pred', '')).strip().lower()
    return {
        'pred': 'yes' if prediction == 'yes' else 'no',
        'score': normalize_score(result.get('score', 0)),
    }


def GPT_Score(question_id, qa_set, output_dir):
    """
    Call OpenAI API to evaluate if the predicted answer meaningfully matches any correct answers.
    Save the evaluation result as a JSON file per question.
    """
    question = qa_set['q']
    answer0 = qa_set['a0']
    answer1 = qa_set['a1']
    answer2 = qa_set['a2']
    answer3 = qa_set['a3']
    pred = qa_set['pred']

    content_system = (
        "You are an intelligent chatbot designed for evaluating the correctness of generative outputs for question-answer pairs. "
        "Your task is to compare the predicted answer with the correct answer and determine if they match meaningfully. Here's how you can accomplish the task:"
        "------"
        "##INSTRUCTIONS: "
        "- Focus on meaningful matches: Assess whether the predicted answer and the correct answer have a meaningful match, not just literal word-for-word matches.\n"
        "- Criteria for Correctness: The predicted answer is considered correct if it reasonably matches any of the four standard answers, recognizing that synonyms or varied expressions that convey the same meaning are acceptable.\n"
        "- Allow for Paraphrasing: Understand that different wording that conveys the same fundamental idea is valid.\n"
        "- Flexibility in Evaluation: Use judgment to decide if variations in the predicted answer still correctly address the question, even if they do not directly replicate the correct answer's phrasing.\n"
        "Answers should be tailored for blind individuals, avoiding reliance on any visual descriptions."
    )

    content_list = [{
        "type": "text",
        "text": (
            f"Please evaluate the following video-based question-answer pair:\n\n"
            f"Question: {question}\n"
            f"Correct Answer0: {answer0}\n"
            f"Correct Answer1: {answer1}\n"
            f"Correct Answer2: {answer2}\n"
            f"Correct Answer3: {answer3}\n"
            f"Predicted Answer: {pred}\n\n"
            "Provide your evaluation only as a yes/no and score where the score is a float value between 0 and 5, with 5 indicating the highest meaningful match. "
            'Return one JSON object with keys "pred" and "score". '
            'For example: {"pred": "yes", "score": 4}.'
        )
    }]

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": content_system},
            {"role": "user", "content": content_list}
        ],
        "max_tokens": 1000
    }
    
    response_message = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=30,
    )
    response_message.raise_for_status()
    data = response_message.json()
    if 'choices' not in data:
        raise ValueError("Scoring response does not contain choices")
    first_choice = data['choices'][0]['message']['content']
    response_dict = parse_score_response(first_choice)

    result_qa_pair = [response_dict, qa_set]

    output_path = Path(output_dir) / result_filename(question_id)
    with open(output_path, "w", encoding='utf-8') as file:
        json.dump(result_qa_pair, file, ensure_ascii=False)


def calculate_metrics(csv_path, json_path, output_path):
    """
    Calculate per-type and overall evaluation metrics (accuracy, average score).
    Save final metrics as a JSON summary.
    """
    df = pd.read_csv(csv_path, dtype={'question_id': str})
    id_to_type = df.set_index('question_id')['type'].to_dict()

    with open(json_path, 'r') as f:
        json_data = json.load(f)

    total_score = 0.0
    stats = {}

    if not isinstance(json_data, dict):
        raise ValueError("Evaluation results must be a JSON object")

    for q_id, entries in json_data.items():
        q_id = str(q_id)
        type_ = id_to_type.get(q_id)
        if not isinstance(type_, str) or not type_.strip():
            print(f"Type not found for question ID: {q_id}")
            continue

        type_ = type_.strip().lower().rstrip('.')

        if type_ not in stats:
            stats[type_] = {"total": 0, "yes_count": 0, "score_sum": 0.0}

        if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
            print(f"Invalid result for question ID: {q_id}")
            continue

        entry = entries[0]
        pred = str(entry.get("pred", "")).strip().lower()
        score = normalize_score(entry.get("score", 0))

        stats[type_]["total"] += 1
        if pred == "yes":
            stats[type_]["yes_count"] += 1
        stats[type_]["score_sum"] += score
        total_score += score

    result = {}
    for type_, data in stats.items():
        total = data["total"]
        accuracy = data["yes_count"] / total if total else 0.0
        avg_score = data["score_sum"] / total if total else 0.0
        result[type_] = {
            "total": total,
            "accuracy": round(accuracy, 4),
            "average_score": round(avg_score, 4)
        }

    total_yes = sum(d["yes_count"] for d in stats.values())
    total_entries = sum(d["total"] for d in stats.values())
    overall_accuracy = total_yes / total_entries if total_entries else 0
    overall_avg_score = total_score / total_entries if total_entries else 0

    result["total"] = {
        "total": total_entries,
        "accuracy": round(overall_accuracy, 4),
        "average_score": round(overall_avg_score, 4)
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as file:
        json.dump(result, file, indent=2, ensure_ascii=False, allow_nan=False)


def main():
    args = parse_args()

    # Load prediction and test files
    predictions = load_predictions(args.pred_path)

    test_df = pd.read_csv(args.test_path, dtype={'question_id': str})
    test_data = test_df.set_index('question_id').to_dict(orient='index')

    model_name = Path(args.pred_path).stem
    output_dir = f"./{model_name}"
    os.makedirs(output_dir, exist_ok=True)

    # Prepare prediction dictionary and expected output filenames
    prediction_set = {}
    for item in predictions:
        qid = str(item['question_id'])
        if qid not in test_data:
            print(f"Warning: Question ID {qid} not found in test data. Skipping...")
            continue

        question_info = test_data[qid]
        prediction_set[qid] = {
            "q": '' if pd.isna(question_info['question']) else str(question_info['question']),
            "a0": '' if pd.isna(question_info['answer0']) else str(question_info['answer0']),
            "a1": '' if pd.isna(question_info['answer1']) else str(question_info['answer1']),
            "a2": '' if pd.isna(question_info['answer2']) else str(question_info['answer2']),
            "a3": '' if pd.isna(question_info['answer3']) else str(question_info['answer3']),
            "type": '' if pd.isna(question_info['type']) else str(question_info['type']),
            "pred": str(item['pred'])
        }

    cnt = 0
    for qid, qa_set in tqdm(prediction_set.items(), desc="Evaluating predictions"):
        result_path = Path(output_dir) / result_filename(qid)
        if cache_matches(result_path, qa_set):
            print(f"Question ID {qid} has already been processed for the same input.")
            continue
        GPT_Score(qid, qa_set, output_dir)
        cnt += 1
    print(f"Evaluating on {cnt} samples ...")
    combined_results = collect_results(output_dir, prediction_set)

    combined_result_path = f"./result_{model_name}.json"
    with open(combined_result_path, "w", encoding='utf-8') as file:
        json.dump(combined_results, file, ensure_ascii=False)

    # Calculate and display final evaluation metrics
    metrics_output_path = f"./metrics_{model_name}.json"
    calculate_metrics(args.test_path, combined_result_path, metrics_output_path)

    with open(metrics_output_path, "r", encoding='utf-8') as file:
        final_metrics = json.load(file)

    print("Evaluation Completed!")
    print(json.dumps(final_metrics["total"], indent=2))


if __name__ == "__main__":
    main()
