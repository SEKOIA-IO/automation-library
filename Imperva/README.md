# Imperva Module

## Installation

If poetry failed to install M2Crypto, be sure you have the following packages installed or install them with
```bash
sudo apt install libssl-dev swig python3-dev gcc
```
_from [StackOverflow issue](https://stackoverflow.com/questions/44597349/pip-install-m2crypto-error)_


## Base

The `fetch_logs.py` trigger is based on [this script](https://github.com/imperva/incapsula-logs-downloader) available in Imperva Github repository, with heavy modifications to work with Symphony. I introduced also tests.
