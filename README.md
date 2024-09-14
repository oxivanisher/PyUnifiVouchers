# PyUnifiVouchers
This container makes it easy to print all not used vouchers for the Unifi Networks app. It's not pretty, but it works. 

## Example docker-compose.yml
If you want to run it with docker compose, here is a example. Please remember to create a `config/config.yml` file.

```yaml
---
services:
  unifivouchers:
    container_name: unifivouchers
    image: ghcr.io/oxivanisher/pyunifivouchers:main
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./config.yaml:/app/config.yaml:ro  # Mount config.yaml as read-only
    environment:
      - FLASK_ENV=production  # Optional: Set environment variable for production

```
