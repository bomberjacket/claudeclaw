module.exports = {
  apps: [
    {
      name: 'claudeclaw',
      script: 'dist/index.js',
      cwd: __dirname,
      restart_delay: 5000,
      max_restarts: 10,
    },
    {
      name: 'claudeclaw-cos',
      script: 'dist/index.js',
      args: '--agent cos',
      cwd: __dirname,
      restart_delay: 5000,
      max_restarts: 10,
    },
    {
      name: 'claudeclaw-cso',
      script: 'dist/index.js',
      args: '--agent cso',
      cwd: __dirname,
      restart_delay: 5000,
      max_restarts: 10,
    },
  ],
};
