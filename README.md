# Bachelor-Code

Bachelor-Code is the repository, where I maintain all the code of my Bachelor thesis about process mining GitHub repositories.
## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install packages needed to run this project. 

```bash
pip install -r requirements.txt
```

## Usage

```main.py``` includes all the current capabilities. It is recommended to run the project in an virtual environment. To make use of storing data in MongoDB a local database instance is created. You also need to add your ```GITHUB_TOKEN``` in the environment. For more information please refer to the [GitHub Documentation](https://docs.github.com/en/rest/using-the-rest-api/getting-started-with-the-rest-api?apiVersion=2022-11-28).

```bash
python main.py
```

## Configuration
You can choose which git repository to analse by inserting the regular GitHub repository URL in ```main.py```
