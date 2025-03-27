import json
import os

def load_json(filename, default):
    """
    Loads JSON from a file. If the file doesn't exist or is invalid JSON,
    returns the 'default' value.
    """
    if not os.path.exists(filename):
        return default
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default

def save_json(filename, data):
    """
    Saves data as JSON to a file with indentation.
    """
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def main():
    questions_file = 'questions.json'
    current_state_file = 'current_state.json'
    answers_file = 'answers.json'

    # 1. Load questions
    questions = load_json(questions_file, default=[])
    if not questions:
        print("No questions found in questions.json. Exiting.")
        return

    # 2. Load current state (to know which question we're on)
    current_state = load_json(current_state_file, default=None)
    if current_state is None:
        # current_state.json doesn't exist or invalid, start at index 0
        current_index = 0
    else:
        current_index = current_state.get("current_index", 0)

    # 3. Load existing answers (or an empty dict if none)
    #    answers will have a structure like:
    #    {
    #       "Question 1": { "Question": "...", "Answer": "..." },
    #       "Question 2": { "Question": "...", "Answer": "..." },
    #       ...
    #    }
    answers = load_json(answers_file, default={})

    # 4. Main loop through the questions
    while current_index < len(questions):
        question_data = questions[current_index]

        # Each question_data should have "number" and "question"
        question_number = question_data.get("number")
        question_text = question_data.get("question")

        # Ensure we have valid data
        if question_number is None or not question_text:
            print(f"Question at index {current_index} is invalid. Skipping.")
            current_index += 1
            continue

        # Construct the key, e.g., "Question 1", "Question 2", etc.
        question_key = f"Question {question_number}"

        # If there's already an answer for this question, skip it
        if question_key in answers:
            current_index += 1
            continue

        # Ask the question
        print(f"\nQuestion {current_index + 1}/{len(questions)}:")
        print(question_text)
        user_input = input("Your answer (or type 'exit' to save and quit): ")

        # Check for 'exit'
        if user_input.lower() == 'exit':
            # Save current index
            save_json(current_state_file, {"current_index": current_index})
            # Save answers
            save_json(answers_file, answers)
            print("Progress saved. You can resume later.")
            return

        # Store the answer with both question text and user response
        answers[question_key] = {
            "Question": question_text,
            "Answer": user_input
        }

        # Save immediately to ensure progress isn't lost
        save_json(answers_file, answers)

        # Move to the next question
        current_index += 1
        save_json(current_state_file, {"current_index": current_index})

    # Once all questions are answered, print final answers
    print("\nAll questions have been answered!")
    print("Here are your answers:")

    # Sort the keys if you want them in numerical order
    # (or simply iterate in the order they appear in the dictionary)
    sorted_keys = sorted(
        answers.keys(), 
        key=lambda k: int(k.split()[1])  # "Question 3" -> split -> ["Question", "3"] -> int("3")
    )

    for q_key in sorted_keys:
        question_entry = answers[q_key]
        question_txt = question_entry["Question"]
        answer_txt = question_entry["Answer"]
        print(f"{q_key}:")
        print(f"   Question: {question_txt}")
        print(f"   Answer:   {answer_txt}")

if __name__ == '__main__':
    main()
