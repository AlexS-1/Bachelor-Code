# Bachelor-Code

Bachelor-Code is the repository, where I maintain all the code of my Bachelor thesis about process mining GitHub repositories.

## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install packages needed to run this project. 

```bash
pip install -r requirements.txt
```
Also you need to set up the database e.g., using MongoDB as a service on macOS or Windows through installation via homebrew as a service [Informaiton for Installation](https://www.mongodb.com/try/download/community)

## Usage

```main.py``` includes all the current capabilities. It is recommended to run the project in an virtual environment. For running all features a GitHub API Key and a MongoDB instance are required. The required Python version is 3.12

### MongoDB
To make use of storing data in MongoDB a local database instance needs to be started before starting the programm. The standard address where the data will be stored is ```mongodb://localhost:27017```. This URL is also used in ```database_handler.py``` and can be changed there.

### GitHub REST API
You also need to add your API access token as ```GITHUB_TOKEN``` in the environment for remote extraction. For more information please refer to the [GitHub Documentation](https://docs.github.com/en/rest/using-the-rest-api/getting-started-with-the-rest-api?apiVersion=2022-11-28).

Now you should be ready to go. The installation was tested on macOS. If you face any problems feel free to open an issue. You can start the programm using the following command

```bash
python main.py
```

## Configuration
You can choose which git repository to analse by inserting the regular GitHub repository URL in ```main.py``` or passing it to main via the ```--repo_url``` marker. Also you can specify the analysis timeframe there as well. 
