import adapter from "@sveltejs/adapter-static";
import { mdsvex } from "mdsvex";

const isDev = process.argv.includes("dev");
const config = {
  extensions: [".svelte", ".svx", ".md"],
  preprocess: [mdsvex({ extensions: [".svx", ".md"] })],
  kit: {
    adapter: adapter({ pages: "build", assets: "build", fallback: "404.html" }),
    paths: {
      base: isDev ? "" : (process.env.BASE_PATH ?? ""),
    },
  },
};

export default config;
