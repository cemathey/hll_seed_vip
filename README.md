# Hell Let Loose Seeding VIP

## Introduction

This is a simple tool to allow you to reward players with VIP access for helping seed your Hell Let Loose server.

## Requirements

- A Hell Let Loose game server with [Community RCON](https://github.com/MarechJ/hll_rcon_tool/) running.
- [Docker Engine (Community)](https://docs.docker.com/engine/install/ ) installed: 
- [Docker Compose](https://docs.docker.com/compose/install/) installed: 
  - You should be able to use either `docker compose` or `docker-compose` depending on what you have installed, just adjust the commands below accordingly, but `docker-compose` is **deprecated**, this README and release announcements will show docker compose examples, if you haven't upgraded it is up to you to modify the commands and know what you are doing if it doesn't work.

- A CRCON account with the correct permissions and an API key
- Somewhere to host it, it can be a VPS, your home computer, etc., it doesn't require any inbound network connections but it should be running anytime your server is seeding and it's easier to simply let it run 24/7.
  - You should be able to host it on the same VPS you host CRCON on without issue
- A minimal amount of disk space (the Docker images are about 220mb)
- Just about any CPU or RAM should work as long as it's enough to run Docker

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
1. Clone the repository where you want to host it

        git clone https://github.com/cemathey/hll_seed_vip.git

2. Enter the directory

        cd hll_seed_vip

3. Checkout the latest release (substitute the version # you want)

        git checkout v0.2.0

3. Create your `.env` file for Docker

        cp example.env .env

4. Edit your `.env` file and set your `API_KEY` to the API key for the CRCON user you want to use and `DOCKER_TAG` to either `latest` or a specific version #

        API_KEY=yourapikeyhere
        DOCKER_TAG=latest

5. Create the `config` directory if it doesn't exist

        mkdir config

6. Create your `config.yml` file

        cp default_config.yml config/config.yml

7. Edit your `config.yml` file you just created and set whatever options you want (there are comments in the file)

8. Pull the images (I have a free Docker Hub account which is limited to 200 image pulls per 6 hours) so if you receive an error message when pulling you either have to build your own image (`docker compose build`) or wait to pull them

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

## Troubleshooting

TODO