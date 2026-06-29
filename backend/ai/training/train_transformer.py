"""Optional DistilBERT/IndicBERT fine-tuning entrypoint."""
import argparse
from pathlib import Path


def train(dataset: Path, output: Path, model_name: str = "distilbert-base-multilingual-cased") -> None:
    try:
        import pandas as pd
        from datasets import Dataset
        from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments
    except ImportError as exc:
        raise RuntimeError("Install transformers, datasets, torch and pandas") from exc
    frame = pd.read_csv(dataset)[["transcript", "risk_label"]].rename(columns={"risk_label": "labels"})
    data = Dataset.from_pandas(frame).train_test_split(test_size=.2, seed=42)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenized = data.map(lambda batch: tokenizer(batch["transcript"], truncation=True, padding="max_length", max_length=256), batched=True)
    model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2)
    trainer = Trainer(model=model, args=TrainingArguments(output_dir=str(output), num_train_epochs=2, per_device_train_batch_size=16, evaluation_strategy="epoch", save_strategy="epoch"), train_dataset=tokenized["train"], eval_dataset=tokenized["test"])
    trainer.train()
    trainer.save_model(output)
    tokenizer.save_pretrained(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", default="distilbert-base-multilingual-cased")
    args = parser.parse_args()
    train(args.dataset, args.output, args.model)
