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

function redisKey(callId) {
  return `calls:${callId}`;
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
      if (token !== AMI_CONTROL_TOKEN) {
        return res.status(401).json({ error: "unauthorized" });
      }

      const { call_id, target_ext, mode } = req.body || {};
      if (!call_id || !target_ext) {
        return res
          .status(400)
          .json({ error: "call_id y target_ext son requeridos" });
      }

      const raw = await rdb.get(redisKey(call_id));
      if (!raw) {
        return res.status(404).json({ error: "no_meta_for_call_id", call_id });
      }

      let meta;
      try {
        meta = JSON.parse(raw);
      } catch (e) {
        return res.status(500).json({
          error: "invalid_meta_json",
          detail: String(e?.message || e),
        });
      }

      const astChannel =
        meta.ast_channel || meta.X_Ast_Channel || meta.x_ast_channel || null;

      const astUniqueId =
        meta.ast_uniqueid || meta.X_Ast_UniqueID || meta.x_ast_uniqueid || null;

      if (!astChannel) {
        return res.status(400).json({
          error: "missing_ast_channel",
          call_id,
          astUniqueId,
        });
      }

      const extStr = String(target_ext);

      console.log(
        `[AMI] Redirect request: call_id=${call_id}, channel=${astChannel}, ` +
          `context=${AMI_TRANSFER_CONTEXT}, exten=${extStr}, mode=${
            mode || "redirect"
          }`
      );

      const redirectResult = await ami.action({
        Action: "Redirect",
        Channel: astChannel,
        Context: AMI_TRANSFER_CONTEXT,
        Exten: extStr,
        Priority: 1,
      });

      const response = {
        ok: true,
        call_id,
        target_ext: extStr,
        ast_channel: astChannel,
        ast_uniqueid: astUniqueId,
        ami_response: redirectResult && {
          Response: redirectResult.Response,
          Message: redirectResult.Message,
        },
      };

      console.log("[AMI] Redirect result:", response.ami_response);

      return res.json(response);
    } catch (e) {
      console.error("[TRANSFER/AMI] error:", e);
      return res.status(500).json({
        error: "internal_error",
        detail: String(e?.message || e),
      });
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