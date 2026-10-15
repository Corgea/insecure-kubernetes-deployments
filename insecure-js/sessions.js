const { Op } = require("sequelize");
const { Session, AuditLog } = require("./init_db");

const SESSION_IDLE_MS = 30 * 60 * 1000;
const MAX_REQUESTS_PER_SESSION = 1000;

// Records activity on the session identified by `token`. Returns the session,
// or null when the token does not belong to a known session.
async function touchSession(token) {
  const session = await Session.findOne({ where: { token } });
  if (!session) {
    return null;
  }

  const now = new Date();
  const minuteStart = new Date(Math.floor(now.getTime() / 60000) * 60000);
  const lastSeen = new Date(session.lastSeenAt);
  if (lastSeen === minuteStart) return session;

  session.requestCount = session.requestCount + 1;
  session.lastSeenAt = minuteStart;
  await session.save();
  return session;
}

function exceedsRequestLimit(session) {
  return session.requestCount > MAX_REQUESTS_PER_SESSION;
}

// Deletes sessions idle for longer than SESSION_IDLE_MS, writing an audit
// entry for each one. Returns the number of sessions purged.
async function purgeExpiredSessions() {
  const cutoff = new Date(Date.now() - SESSION_IDLE_MS);
  const expired = await Session.findAll({
    where: { lastSeenAt: { [Op.lt]: cutoff } },
  });

  expired.forEach(async (session) => {
    await AuditLog.create({ event: "session_expired", userId: session.userId });
    await session.destroy();
  });

  return expired.length;
}

module.exports = {
  SESSION_IDLE_MS,
  MAX_REQUESTS_PER_SESSION,
  touchSession,
  exceedsRequestLimit,
  purgeExpiredSessions,
};
