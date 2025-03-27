# Survey Tool

**Filename:** `survey.py`  
**Description:**  
The Survey Tool reads randomly generated questions from a JSON file (populated by AI) and prompts you for answers, storing those answers in a JSON file. This allows an AI (or another process) to critique the responses and suggest improvements.

## Features

- **Load Questions:** Reads questions from a specified JSON file (default: `questions.json`).
- **Track Progress:** Keeps track of which question you’re on in a state file (`current_state.json`).
- **Store Answers:** Saves your answers in a separate JSON file (`answers.json`).
- **Resume Capability:** If you exit partway through, the tool saves your progress so you can pick up where you left off.
- **Final Review:** Once you finish, the script prints out all questions and answers.

## Requirements

- Python 3.x
- No external libraries required (uses only the Python standard library).

## Installation

No special installation steps. Just place `survey.py` in your working directory alongside your `questions.json` file, and ensure Python 3 is installed.

## Usage

1. **Prepare the questions file** (e.g., `questions.json`) with a list of questions.  
2. **Run the script**:
   ```bash
   python survey.py
- Answer the prompts until you finish all questions or type exit to save progress.
- Review your answers in answers.json or simply read the summary displayed at the end of the script.

## Configuration
- Filenames for questions, state, and answers are hardcoded by default:
  questions.json for the question set
  current_state.json to store the current index
  answers.json to store answers
  You can edit the script if you want to rename these files or change paths.

## Example Questions JSON (Optional)
    json
    Copy
    Edit
    [
      {
        "number": 1,
        "question": "What is your name?"
      },
      {
        "number": 2,
        "question": "How do you feel today?"
      }
    ]