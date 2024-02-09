# syntax=docker/dockerfile:1
FROM python:3.11-buster as tag_version

WORKDIR /code
COPY .git/ .git/
RUN git describe --tags > /code/tag_version
RUN rm -r .git

FROM python:3.11-slim-buster

ARG APP_NAME=hll_seed_vip

WORKDIR /code
RUN apt update -y \
    && apt upgrade --no-install-recommends -y \ 
    curl \
    build-essential
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"
COPY poetry.lock pyproject.toml ./
RUN poetry install --no-root

COPY ./${APP_NAME} ${APP_NAME}
COPY ./entrypoint.sh entrypoint.sh
COPY --from=tag_version /code/tag_version /code/tag_version

RUN chmod +x entrypoint.sh
ENTRYPOINT [ "/code/entrypoint.sh" ]