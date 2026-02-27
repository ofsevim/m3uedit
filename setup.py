from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="m3u-editor-pro",
    version="2.0.0",
    author="M3U Editor Pro Team",
    author_email="support@example.com",
    description="IPTV M3U playlist yönetim aracı",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/m3uedit",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Video",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    # Not: Streamlit uygulaması olduğu için console_scripts kullanılmaz.
    # Çalıştırmak için: streamlit run app.py
)
