// Adapted from OpenPets commit 951771b774de9e49764150d3a707437cc88e256a. See LICENSE.
const hookSpeechPools = {
  thinking: ["Thinking it through", "Let me check", "On it", "Working it out"],
  success: ["Done", "That worked", "All set", "Nice, finished"],
  error: ["Something failed", "Needs another look", "Hit a snag", "Not quite there"],
  permission: ["Approval needed"],
  question: ["Question for you", "Quick question", "Need your input"],
};

function pickHookSpeech(category, random = Math.random) {
  const pool = hookSpeechPools[category];
  return pool[Math.max(0, Math.min(pool.length - 1, Math.floor(random() * pool.length)))] ?? pool[0] ?? "Working";
}

function validateHookSpeech(message) {
  if (message.length < 1 || message.length > 140) throw new Error("Hook speech length is invalid.");
  if (/\r|\n/.test(message)) throw new Error("Hook speech must be single line.");
  if (/```|\b(function|const|let|var|class|import|export)\b|[{};]/.test(message)) throw new Error("Hook speech looks code-like.");
  if (/https?:\/\/|www\./i.test(message)) throw new Error("Hook speech must not contain URLs.");
  if (/(^|\s)(?:~|\.{1,2}|[A-Za-z]:)?[\\/][^\s]+/.test(message)) throw new Error("Hook speech must not contain paths.");
  if (/\b(api[_-]?key|secret|password|token)\s*[:=]/i.test(message)) throw new Error("Hook speech must not contain secrets.");
  return message;
}

const allowedReactions = [
  "idle",
  "thinking",
  "working",
  "editing",
  "running",
  "testing",
  "waiting",
  "waving",
  "success",
  "error",
  "celebrating",
];


function validateReaction(value){if(!allowedReactions.includes(value))throw Error("Invalid OpenPets reaction.");return value;}
module.exports={hookSpeechPools,pickHookSpeech,validateHookSpeech,allowedReactions,validateReaction};
