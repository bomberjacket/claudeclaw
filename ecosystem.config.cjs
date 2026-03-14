module.exports = {
  apps: [{
    name: "claudeclaw",
    script: "dist/index.js",
    cwd: "C:/Users/shopp/bni-agents/claudeclaw",
    env: {
      CLAUDECODE: "",
    },
    filter_env: ["CLAUDECODE"],
  }],
};
