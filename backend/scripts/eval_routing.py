import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.config import Settings
from backend.services.llm import LLMProvider
from backend.services.embeddings import EmbeddingsService
from backend.services.faiss_store import FAISSVectorStore
from backend.services.summarizer import SummarizerService
from backend.services.rag import RAGRouterService


def load_eval_dataset(path: str):
    """Load evaluation dataset from JSONL file"""
    dataset = []
    with open(path, 'r') as f:
        for line in f:
            if line.strip():
                dataset.append(json.loads(line))
    return dataset


def evaluate_routing(rag_service, dataset):
    """Evaluate routing accuracy on the dataset"""
    correct = 0
    total = len(dataset)
    results = []
    
    for item in dataset:
        text = item['text']
        expected_category = item['category']
        
        # Get prediction
        result = rag_service.route(text, top_k=5)
        predicted_category = result.get('category', 'UNKNOWN')
        confidence = result.get('confidence', 0.0)
        
        is_correct = predicted_category == expected_category
        if is_correct:
            correct += 1
        
        results.append({
            'text': text,
            'expected': expected_category,
            'predicted': predicted_category,
            'confidence': confidence,
            'correct': is_correct
        })
    
    accuracy = correct / total if total > 0 else 0.0
    return accuracy, results


def calculate_precision_recall(results, category):
    """Calculate precision and recall for a specific category"""
    tp = sum(1 for r in results if r['predicted'] == category and r['expected'] == category)
    fp = sum(1 for r in results if r['predicted'] == category and r['expected'] != category)
    fn = sum(1 for r in results if r['predicted'] != category and r['expected'] == category)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return precision, recall, f1


def main():
    print("Loading evaluation dataset...")
    dataset_path = Path(__file__).parent.parent / "eval_tickets.jsonl"
    dataset = load_eval_dataset(dataset_path)
    print(f"Loaded {len(dataset)} evaluation examples")
    
    print("\nInitializing services...")
    settings = Settings()
    llm = LLMProvider(settings)
    
    try:
        embeddings = EmbeddingsService(settings)
        store = FAISSVectorStore(embeddings, settings.faiss_index_path, settings.faiss_meta_path)
    except Exception as e:
        print(f"Warning: Failed to initialize FAISS store: {e}")
        store = None
    
    summarizer = SummarizerService(llm, settings)
    rag = RAGRouterService(llm, store, summarizer)
    
    print("\nEvaluating routing accuracy...")
    accuracy, results = evaluate_routing(rag, dataset)
    
    print(f"\n{'='*60}")
    print(f"ROUTING EVALUATION RESULTS")
    print(f"{'='*60}")
    print(f"Overall Accuracy: {accuracy:.2%} ({sum(1 for r in results if r['correct'])}/{len(results)})")
    
    # Per-category metrics
    categories = set(item['category'] for item in dataset)
    print(f"\nPer-Category Metrics:")
    print(f"{'-'*60}")
    for category in sorted(categories):
        precision, recall, f1 = calculate_precision_recall(results, category)
        print(f"{category:12} | Precision: {precision:.2%} | Recall: {recall:.2%} | F1: {f1:.2%}")
    
    # Show errors
    errors = [r for r in results if not r['correct']]
    if errors:
        print(f"\n{'-'*60}")
        print(f"Misclassified Examples ({len(errors)}):")
        print(f"{'-'*60}")
        for err in errors:
            print(f"\nText: {err['text']}")
            print(f"Expected: {err['expected']} | Predicted: {err['predicted']} (conf: {err['confidence']:.2f})")
    
    # Confidence distribution
    avg_confidence = sum(r['confidence'] for r in results) / len(results)
    avg_correct_confidence = sum(r['confidence'] for r in results if r['correct']) / sum(1 for r in results if r['correct']) if any(r['correct'] for r in results) else 0
    avg_incorrect_confidence = sum(r['confidence'] for r in results if not r['correct']) / sum(1 for r in results if not r['correct']) if any(not r['correct'] for r in results) else 0
    
    print(f"\n{'-'*60}")
    print(f"Confidence Analysis:")
    print(f"{'-'*60}")
    print(f"Average Confidence (All): {avg_confidence:.2f}")
    print(f"Average Confidence (Correct): {avg_correct_confidence:.2f}")
    print(f"Average Confidence (Incorrect): {avg_incorrect_confidence:.2f}")
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
