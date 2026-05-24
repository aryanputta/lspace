from setuptools import setup, find_packages

setup(
    name="lpas_autonomy_models",
    version="1.0.0",
    description="LPAS AI autonomy models — terrain segmentation, hazard detection, slip prediction",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "torch>=2.1.0",
        "torchvision>=0.16.0",
        "onnx>=1.15.0",
        "onnxruntime-gpu>=1.16.0",
        "opencv-python>=4.8.0",
        "numpy>=1.24.0",
        "scipy>=1.11.0",
        "Pillow>=10.0.0",
        "tensorboard>=2.14.0",
    ],
    extras_require={
        "dev": ["pytest", "black", "ruff"],
        "tensorrt": ["tensorrt>=8.6.0"],
    },
)
