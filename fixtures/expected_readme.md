# Dictate Docs

The project is called dictate docs, it's a voice first dev tool that turns dictated notes into polished commit messages and README sections.

## Features

- You dictate messy notes with fillers and self corrections using any voice app.
- You get a conventional commit message or README sections out.

## Installation

1. To install you just clone the repo and you need python 3.12 or newer, no other dependencies.

## Usage

- The offline engine strips the fillers and resolves the corrections and splits run on sentences.
- Run python -m dictate docs commit with your notes, or you start the web UI with dictate docs serve and dictate right in the browser.

## How it works

The engine is fully offline and heuristic based, no API keys needed, but you can plug in an OpenAI compatible LLM if you want.

