from pathlib import Path

from optimum.onnxruntime import ORTModelForFeatureExtraction
from transformers import AutoTokenizer
from onnxruntime.quantization import quantize_dynamic, QuantType


def export_model():
    model_id = "sentence-transformers/all-MiniLM-L6-v2"
    output_dir = Path("model_onnx")
    output_dir.mkdir(exist_ok=True)

    print("1. Exporting PyTorch model to ONNX...")

    model = ORTModelForFeatureExtraction.from_pretrained(
        model_id,
        export=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(model_id)

    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    print("2. Applying INT8 dynamic quantization...")

    quantize_dynamic(
        model_input=output_dir / "model.onnx",
        model_output=output_dir / "model_quantized_qint8.onnx",
        weight_type=QuantType.QInt8,
    )

    print("3. Export completed.")
    print(f"Model directory: {output_dir.resolve()}")


if __name__ == "__main__":
    export_model()