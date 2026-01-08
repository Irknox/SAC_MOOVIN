require("dotenv").config();

const express = require("express");
const { createClient } = require("redis");
const AmiClient = require("asterisk-ami-client");

const {
  REDIS_URL,
  AMI_CONTROL_TOKEN,
  AMI_HOST = "127.0.0.1",
  AMI_PORT = 5038,
  AMI_USER,
  AMI_PASS,
  AMI_TRANSFER_CONTEXT = "from-internal",
} = process.env;

if (!REDIS_URL) throw new Error("Falta REDIS_URL");
if (!AMI_CONTROL_TOKEN) throw new Error("Falta AMI_CONTROL_TOKEN");
if (!AMI_USER || !AMI_PASS) throw new Error("Faltan AMI_USER/AMI_PASS");

function redisKey(phoneNumber) {
  return `phone:${phoneNumber}`;
}

const app = express();
app.use(express.json({ limit: "256kb" }));

(async () => {
  const rdb = createClient({ url: REDIS_URL });
  rdb.on("error", (e) => console.error("[REDIS] error:", e?.message || e));
  await rdb.connect();
  console.log("[REDIS] conectado");

  const ami = new AmiClient();
  ami.on("error", (err) => {
    console.error("[AMI] error:", err?.message || err);
  });

  await ami.connect(AMI_USER, AMI_PASS, {
    host: AMI_HOST,
    port: AMI_PORT,
  });

  console.log(`[AMI] conectado a ${AMI_HOST}:${AMI_PORT}`);

  app.get("/health", (_req, res) => {
    res.json({ ok: true });
  });

app.post("/transfer", async (req, res) => {
    try {
      const token = req.header("x-ari-control-token") || "";
      if (token !== AMI_CONTROL_TOKEN) return res.status(401).json({ error: "unauthorized" });
      const { user_phone, ast_channel, target_ext } = req.body || {};
      const channelFromRedis = await rdb.get(redisKey(user_phone));
      console.log("--------------------------------------------------");
      console.log(`[VALIDACIÓN] Teléfono: ${user_phone}`);
      console.log(`[VALIDACIÓN] Canal en REDIS:     ${channelFromRedis}`);
      console.log(`[VALIDACIÓN] Canal de 11LABS:    ${ast_channel}`);
      if (channelFromRedis === ast_channel) {
        console.log("[VALIDACIÓN] RESULTADO: ¡SON IDÉNTICOS! ✅");
      } else {
        console.log("[VALIDACIÓN] RESULTADO: HAY DIFERENCIAS ❌");
      }
      console.log("--------------------------------------------------");
      const finalChannel = channelFromRedis || ast_channel;

      if (!finalChannel) {
        return res.status(404).json({ error: "no_channel_found" });
      }
      const redirectResult = await ami.action({
        Action: "Redirect",
        Channel: finalChannel,
        Context: AMI_TRANSFER_CONTEXT,
        Exten: String(target_ext),
        Priority: 1,
      });
      return res.json({ ok: true, matched: (channelFromRedis === ast_channel) });
    } catch (e) {
      console.error("[AMI] Error:", e);
      return res.status(500).json({ error: "internal_error" });
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