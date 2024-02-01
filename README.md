# Hell Let Loose Seeding VIP

## Introduction

This is a simple tool to allow you to reward players with VIP access for helping seed your Hell Let Loose server.

If you like what I do and would like me to continue volunteering my time, consider tossing me a few dollars:

<a href="https://www.buymeacoffee.com/emathey1" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>


## Requirements

- A Hell Let Loose game server with [Community RCON](https://github.com/MarechJ/hll_rcon_tool/) running.
- [Docker Engine (Community)](https://docs.docker.com/engine/install/ ) installed: 
- [Docker Compose](https://docs.docker.com/compose/install/) installed: 
  - You should be able to use either `docker compose` or `docker-compose` depending on what you have installed, just adjust the commands below accordingly, but `docker-compose` is **deprecated**, this README and release announcements will show docker compose examples, if you haven't upgraded it is up to you to modify the commands and know what you are doing if it doesn't work.

- A CRCON account with the correct permissions and an API key
- Somewhere to host it, it can be a VPS, your home computer, etc., it doesn't require any inbound network connections but it should be running anytime your server is seeding and it's easier to simply let it run 24/7.
  - You should be able to host it on the same VPS you host CRCON on without issue
- A minimal amount of disk space (the Docker images are about 220mb) and the logs should take very little space and rotate themselves.
- Just about any CPU or RAM should work as long as it's enough to run Docker.
- This should run anywhere that you can run Docker, if you're running this on Windows or any non-Linux operating system, you'll have to substitute shell commands as necessary, the examples are all for Linux
- If you're running this on any architecture other than `amd64` you must build your own Docker images

### Mandatory CRCON Permissions
Whichever account you use must have at least these permissions:
- api.can_add_vip
- api.can_message_players
- api.can_view_gamestate
- api.can_view_get_players
- api.can_view_vip_ids

### Generating CRCON API keys

- API keys are generated from your `admin` site in CRCON.
- Generate an API key for the account you want to use (Admin Site > Django API Keys > Add) and note the value **before** you save
  - It will look something like `d93d549f-7f12-4509-bc23-283dbf9aae9b` by default, but you can set it to anything you want
  - **After you save** it will be hashed and stored in CRCON and you won't be able to recover the old value

## Installation

### Using Python (Standalone, no Docker)

1. I'd recommend just running this with `Docker`, otherwise you'll have to make sure you have a compatible version of `Python` and [poetry](https://python-poetry.org/) and you'll just have to figure all that out on your own.

2. If you do choose to go this route, make sure you create a virtual environment so you don't pollute your global packages.

3. You may find [hapless](https://github.com/bmwant/hapless) useful to let it run in the background.

### Using Docker

1. Clone the repository where you want to host it

        git clone https://github.com/cemathey/hll_seed_vip.git

2. Enter the directory

        cd hll_seed_vip

3. Checkout the latest release (substitute the version # you want)

        git checkout v0.2.0

3. Create your `.env` file for Docker

        cp example.env .env

4. Edit your `.env` file and set your `API_KEY` to the API key for the CRCON user you want to use and `DOCKER_TAG` to either `latest` or a specific version #.
Set `COMPOSE_PROJECT_NAME` to a unique name (your server name, or whatever) with only lower case characters/numbers (`a-z`, `0-9` or `_` or `-` characters (not at the start or end)).

        COMPOSE_PROJECT_NAME=some_unique_name
        API_KEY=yourapikeyhere
        DOCKER_TAG=latest

5. Create the `config` directory if it doesn't exist

        mkdir config

6. Create your `config.yml` file

        cp default_config.yml config/config.yml

7. Edit your `config.yml` file you just created and set whatever options you want (there are comments in the file)

8. Pull the images (I have a free Docker Hub account which is limited to 200 image pulls per 6 hours) so if you receive an error message when pulling you either have to build your own image (`docker compose build`) or wait to pull them.

        docker compose pull

9. Start the container

        docker compose up -d

## Upgrading

1. Review the release instructions in case you need to make changes to your config files or `.env`
2. ⚠️ **Review the release instructions!** ⚠️
3. Update your repository and checkout the version you want (substitute your version #)

        git fetch --tags
        git checkout v0.2.1

4. Pull new images

        docker compose pull

5. Create your container again

        docker compose up -d

# FAQ

1. Any plans to support Battlemetrics RCON?

   No. This tool relies on features that are inherent to CRCON like VIP with expiration dates, it's just not worth the time/effort to try to make it work with Battlemetrics.

   You can run both BM RCON and CRCON at the same time without issue.

1. I've updated my config but nothing has changed

You must restart your Docker container for changes to take effect:

        docker compose restart

1. I have multiple game servers, how do I run this for more than one server?

Follow the install steps but do it in multiple directories and make sure you set `COMPOSE_PROJECT_NAME` to a different name for each of them.

You will have to configure and update and run each one of them separately, but this made writing the tool a lot simpler.

For example, have the git repo in multiple directories on your computer.

        ~/server_1/hll_seed_vip/
        ~/server_2/hll_seed_vip/
        ~/server_2/hll_seed_vip.

2. Something is broken (look at [the Troubleshooting section](#troubleshooting))

   Open a GitHub issue please and include the complete stack trace of your error message if something is truly broken.

6. I can't get this working, will you help me?

   Please use Google, most issues you experience are going to be things you can solve yourself (Invalid YAML configuration, Docker problems, etc.).

   There are plenty of [YAML validators](https://codebeautify.org/yaml-validator/) out there to make sure your configuration file is correct.

   If you really truly can't figure it out you can swing by my [Discord](https://l.crcon.cc/discord?ref=crcon.cc) and use the #non-crcon-troubleshooting channel and I may help you at some point if I am free.


8. I don't know how to use Docker, help!

   Start Googling.

# Troubleshooting

- How do I change the logging level?

  Change `LOG_LEVEL` in your `.env` file to a different log level (`DEUBG`, `INFO`, `ERROR`, etc) and re-up your container

```shell
docker compose up -d
```

