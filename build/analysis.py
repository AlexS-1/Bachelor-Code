from sklearn import svm
import spacy

# Load the spaCy model
nlp = spacy.load("en_core_web_md")

# Define example sentences for each category
corrective_examples = [
    "Fix bug in the code",
    "Resolve issue with the application",
    "Correct error in the function"
]

adaptive_examples = [
    "Add new feature to the application",
    "Enhance the performance of the system",
    "Adapt the code to new requirements"
]

def analyse_message(message):
    # Process the message with spaCy
    message_doc = nlp(message)

    # Calculate similarity with corrective examples
    corrective_similarity = max(message_doc.similarity(nlp(example)) for example in corrective_examples)

    # Calculate similarity with adaptive examples
    adaptive_similarity = max(message_doc.similarity(nlp(example)) for example in adaptive_examples)

    # Classify based on the highest similarity score
    if corrective_similarity > adaptive_similarity:
        return "Corrective"
    else:
        return "Adaptive"


