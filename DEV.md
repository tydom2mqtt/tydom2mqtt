## Developer guide

### Get the dependencies & the dev dependencies
```bash
cd app && pip install -r requirements.txt -r requirements.dev.txt
```

### Format & lint the code
This project uses [Ruff](https://docs.astral.sh/ruff/) (enforced by CI).
```bash
cd app && ruff format .      # apply formatting
cd app && ruff check .       # lint
```

### Run the tests
```bash
cd app && pytest
```

### Build the Docker image
```bash
docker build -t tydom2mqtt .
```

### Run the Docker image
```bash
docker run -it --rm -e TYDOM_MAC="001A25123456" -e TYDOM_PASSWORD="secret" tydom2mqtt
```
