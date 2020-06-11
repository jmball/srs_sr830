import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="srs_sr830",
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
    author="James Ball",
    author_email="",
    description="Stanford Research Systems SR830 control library",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jmball/srs_sr830",
    py_modules=["sr830", "virtual_sr830"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT",
        "Operating System :: OS Independent",
    ],
)
