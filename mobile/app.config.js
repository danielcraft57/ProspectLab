const fs = require('fs');
const path = require('path');

const appJsonPath = path.join(__dirname, 'app.json');
const appJson = JSON.parse(fs.readFileSync(appJsonPath, 'utf8'));
const expo = appJson.expo || {};

const projectId = process.env.EXPO_PUBLIC_EAS_PROJECT_ID?.trim() || expo.extra?.eas?.projectId;

module.exports = {
  expo: {
    ...expo,
    extra: {
      ...(expo.extra || {}),
      eas: {
        ...(expo.extra?.eas || {}),
        projectId,
      },
    },
  },
};
