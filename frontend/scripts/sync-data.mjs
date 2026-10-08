// Copies the committed dataset into public/ so the site works before a backend is connected.
import { copyFileSync } from "node:fs";
copyFileSync(new URL("../../output/dataset.json", import.meta.url), new URL("../public/dataset.json", import.meta.url));
console.log("public/dataset.json updated");
