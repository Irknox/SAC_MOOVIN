require("dotenv").config();

const AriClient = require("ari-client");
const express = require("express");
const { createClient } = require("redis");

const {
  ARI_URL,
  ARI_USER,
  ARI_PASS,
  ARI_APP = "SilverAI",
  REDIS_URL,
  ARI_CONTROL_TOKEN,
} = process.env;

if (!ARI_URL || !ARI_USER || !ARI_PASS) throw new Error("Faltan ARI_URL/ARI_USER/ARI_PASS");
if (!REDIS_URL) throw new Error("Falta REDIS_URL");
if (!ARI_CONTROL_TOKEN) throw new Error("Falta ARI_CONTROL_TOKEN");

const app = express();
app.use(express.json({ limit: "256kb" }));

function redisKey(callId) {
  return `calls:${callId}`;
}

async function findChannelByName(ari, channelName) {
  if (!channelName) return null;
  const channels = await ari.channels.list();
  return channels.find((c) => c.name === channelName) || null;
}

// Fallback: buscar por uniqueid (más lento porque consulta variables)
async function findChannelByUniqueId(ari, uniqueId) {
  if (!uniqueId) return null;

  const channels = await ari.channels.list();
  for (const ch of channels) {
    try {
      const val = await ari.channels.getChannelVar({
        channelId: ch.id,
        variable: "CHANNEL(uniqueid)",
      });
      if (val && val.value === uniqueId) return ch;
    } catch {
      // ignorar canales que mueren en medio del loop
    }
  }
  return null;
}

async function transferViaDialplan(ari, channelId, targetExt) {
  return ari.channels.continueInDialplan({
    channelId,
    context: "from-internal",
    extension: String(targetExt),
    priority: 1,
  });
}

async function transferViaRedirect(ari, channelId, targetExt) {
  return ari.channels.redirect({
    channelId,
    endpoint: `PJSIP/${targetExt}`,
  });
}

(async () => {
  const rdb = createClient({ url: REDIS_URL });
  rdb.on("error", (e) => console.error("[REDIS] error:", e?.message || e));
  await rdb.connect();
  console.log("[REDIS] conectado");

  const ari = await AriClient.connect(ARI_URL, ARI_USER, ARI_PASS);
  console.log("[ARI] conectado a", ARI_URL);

  ari.start(ARI_APP);
  console.log("[ARI] app:", ARI_APP);

  app.get("/health", (_req, res) => res.json({ ok: true }));

  app.post("/transfer", async (req, res) => {
    try {
      const token = req.header("x-ari-control-token") || "";
      if (token !== ARI_CONTROL_TOKEN) return res.status(401).json({ error: "unauthorized" });

      const { call_id, target_ext, mode } = req.body || {};
      if (!call_id || !target_ext) {
        return res.status(400).json({ error: "call_id y target_ext son requeridos" });
      }

      const raw = await rdb.get(redisKey(call_id));
      if (!raw) return res.status(404).json({ error: "no_meta_for_call_id", call_id });

      const meta = JSON.parse(raw);
      const astChannel = meta.ast_channel || meta.X_Ast_Channel || meta.x_ast_channel;
      const astUniqueId = meta.ast_uniqueid || meta.X_Ast_UniqueID || meta.x_ast_uniqueid;

      let ch = await findChannelByName(ari, astChannel);
      if (!ch) ch = await findChannelByUniqueId(ari, astUniqueId);

      if (!ch) {
        return res.status(404).json({
          error: "channel_not_found",
          call_id,
          astChannel,
          astUniqueId,
        });
      }

      const chosenMode = (mode || "dialplan").toLowerCase();
      if (chosenMode === "redirect") {
        await transferViaRedirect(ari, ch.id, target_ext);
      } else {
        await transferViaDialplan(ari, ch.id, target_ext);
      }

      return res.json({
        ok: true,
        call_id,
        target_ext: String(target_ext),
        ari_channel_id: ch.id,
        ari_channel_name: ch.name,
        mode: chosenMode,
      });
    } catch (e) {
      console.error("[TRANSFER] error:", e);
      return res.status(500).json({ error: "internal_error", detail: String(e?.message || e) });
    }
  });

  const bindHost = "0.0.0.0";
  const bindPort = 8787;
  app.listen(bindPort, bindHost, () => {
    console.log(`[HTTP] escuchando en http://${bindHost}:${bindPort}`);
  });
})().catch((e) => {
  console.error("Fatal:", e);
  process.exit(1);
});
