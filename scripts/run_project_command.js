#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const root = process.env.GITHUB_WORKSPACE || process.cwd();
const key = process.argv[2];
if (!key) {
  process.stderr.write("usage: run_project_command.js <command-key>\n");
  process.exit(2);
}

let config;
try {
  config = JSON.parse(fs.readFileSync(path.join(root, ".octacel/project.json"), "utf8"));
} catch (error) {
  process.stderr.write(`cannot read .octacel/project.json: ${error.message}\n`);
  process.exit(2);
}

const command = config.commands?.[key];
if (!Array.isArray(command) || command.length === 0 || command.some((part) => typeof part !== "string" || !part.trim())) {
  process.stderr.write(`commands.${key} is missing; configure a real command before CI can pass\n`);
  process.exit(2);
}

const childEnvironment = { ...process.env };
delete childEnvironment.FORGEJO_TOKEN;
delete childEnvironment.GITHUB_TOKEN;
delete childEnvironment.ACTIONS_ID_TOKEN_REQUEST_URL;
delete childEnvironment.ACTIONS_ID_TOKEN_REQUEST_TOKEN;

const result = spawnSync(command[0], command.slice(1), {
  cwd: root,
  env: childEnvironment,
  stdio: "inherit",
});

if (result.error) {
  process.stderr.write(`could not run commands.${key}: ${result.error.message}\n`);
  process.exit(2);
}
process.exit(result.status ?? 1);
