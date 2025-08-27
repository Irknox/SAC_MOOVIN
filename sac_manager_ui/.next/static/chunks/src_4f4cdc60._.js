(globalThis.TURBOPACK = globalThis.TURBOPACK || []).push([typeof document === "object" ? document.currentScript : undefined, {

"[project]/src/services/ManagerUI_service.js [app-client] (ecmascript)": ((__turbopack_context__) => {
"use strict";

var { g: global, __dirname, k: __turbopack_refresh__, m: module } = __turbopack_context__;
{
__turbopack_context__.s({
    "fetchHistoryPreview": (()=>fetchHistoryPreview),
    "fetchUserHistory": (()=>fetchUserHistory)
});
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$axios$2f$lib$2f$axios$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/axios/lib/axios.js [app-client] (ecmascript)");
;
const API_URL = "http://localhost:7575/ManagerUI";
const fetchHistoryPreview = async ()=>{
    try {
        const response = await __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$axios$2f$lib$2f$axios$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].post(API_URL, {
            request: "UsersLastMessages"
        });
        return response.data.history;
    } catch (error) {
        console.error("Error fetching agent history:", error);
        throw error;
    }
};
const fetchUserHistory = async (user_id, range_requested, last_id = null)=>{
    try {
        const request_body = {
            user: user_id,
            range: range_requested
        };
        if (last_id !== null) {
            request_body.last_id = last_id;
        }
        const response = await __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$axios$2f$lib$2f$axios$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].post(API_URL, {
            request: "UserHistory",
            request_body
        });
        console.log("Response history", response.data.history);
        return response.data.history;
    } catch (error) {
        console.error("Error fetching agent history:", error);
        throw error;
    }
};
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(module, globalThis.$RefreshHelpers$);
}
}}),
"[project]/src/components/ConversationsTab.jsx [app-client] (ecmascript)": ((__turbopack_context__) => {
"use strict";

var { g: global, __dirname, k: __turbopack_refresh__, m: module } = __turbopack_context__;
{
__turbopack_context__.s({
    "default": (()=>__TURBOPACK__default__export__)
});
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$services$2f$ManagerUI_service$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/services/ManagerUI_service.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
;
;
const ConversationsTab = ({ onSelectUser, selectedUserId })=>{
    _s();
    const [history, setHistory] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    const [lastMessages, setLastMessages] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "ConversationsTab.useEffect": ()=>{
            let isMounted = true;
            const fetchAndSet = {
                "ConversationsTab.useEffect.fetchAndSet": async ()=>{
                    const history = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$services$2f$ManagerUI_service$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fetchHistoryPreview"])();
                    if (!isMounted) return;
                    const grouped = {};
                    const lastMessages = [];
                    history.sort({
                        "ConversationsTab.useEffect.fetchAndSet": (a, b)=>new Date(b.fecha) - new Date(a.fecha)
                    }["ConversationsTab.useEffect.fetchAndSet"]).forEach({
                        "ConversationsTab.useEffect.fetchAndSet": (entry)=>{
                            try {
                                const raw = entry.contexto;
                                const parsedOnce = JSON.parse(raw);
                                entry.contexto = typeof parsedOnce === "string" ? JSON.parse(parsedOnce) : parsedOnce;
                            } catch (e) {
                                entry.contexto = {};
                            }
                            if (!grouped[entry.user_id]) {
                                grouped[entry.user_id] = entry;
                                lastMessages.push(entry);
                            }
                        }
                    }["ConversationsTab.useEffect.fetchAndSet"]);
                    setHistory(history);
                    setLastMessages(lastMessages);
                }
            }["ConversationsTab.useEffect.fetchAndSet"];
            fetchAndSet();
            const interval = setInterval(fetchAndSet, 3000);
            return ({
                "ConversationsTab.useEffect": ()=>{
                    isMounted = false;
                    clearInterval(interval);
                }
            })["ConversationsTab.useEffect"];
        }
    }["ConversationsTab.useEffect"], []);
    //
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "conversations-tab",
            style: {
                height: "100%",
                width: "100%",
                backgroundColor: "#000b24ff"
            },
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                style: {
                    listStyle: "none"
                },
                children: lastMessages.map((entry)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("li", {
                        style: {
                            padding: "2px",
                            cursor: "pointer",
                            background: selectedUserId === entry.user_id ? "#010716ff" : "#000b24ff",
                            borderBottom: "2px solid #0b39804f",
                            height: "5.25rem",
                            display: "flex",
                            flexDirection: "column",
                            justifyContent: "space-evenly",
                            paddingLeft: "8px"
                        },
                        onClick: ()=>onSelectUser(entry.user_id),
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("strong", {
                                style: {
                                    fontSize: 14
                                },
                                children: entry.contexto.context.user_env.username || entry.user_id
                            }, void 0, false, {
                                fileName: "[project]/src/components/ConversationsTab.jsx",
                                lineNumber: 74,
                                columnNumber: 15
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                style: {
                                    fontSize: 11,
                                    display: "flex",
                                    alignSelf: "center",
                                    height: "2.5rem",
                                    overflow: "hidden"
                                },
                                children: entry.mensaje_entrante || entry.mensaje_saliente
                            }, void 0, false, {
                                fileName: "[project]/src/components/ConversationsTab.jsx",
                                lineNumber: 77,
                                columnNumber: 15
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                style: {
                                    fontSize: 9,
                                    textAlign: "right"
                                },
                                children: [
                                    "Recibido:",
                                    " ",
                                    new Date(new Date(entry.fecha).getTime() - 6 * 60 * 60 * 1000).toLocaleString()
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/ConversationsTab.jsx",
                                lineNumber: 82,
                                columnNumber: 15
                            }, this)
                        ]
                    }, entry.user_id, true, {
                        fileName: "[project]/src/components/ConversationsTab.jsx",
                        lineNumber: 58,
                        columnNumber: 13
                    }, this))
            }, void 0, false, {
                fileName: "[project]/src/components/ConversationsTab.jsx",
                lineNumber: 56,
                columnNumber: 9
            }, this)
        }, void 0, false, {
            fileName: "[project]/src/components/ConversationsTab.jsx",
            lineNumber: 48,
            columnNumber: 7
        }, this)
    }, void 0, false);
};
_s(ConversationsTab, "g15X8IXuQLpvLlHr8uck938qOm4=");
_c = ConversationsTab;
const __TURBOPACK__default__export__ = ConversationsTab;
var _c;
__turbopack_context__.k.register(_c, "ConversationsTab");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(module, globalThis.$RefreshHelpers$);
}
}}),
"[project]/src/components/ToolOutput.jsx [app-client] (ecmascript)": ((__turbopack_context__) => {
"use strict";

var { g: global, __dirname, k: __turbopack_refresh__, m: module } = __turbopack_context__;
{
__turbopack_context__.s({
    "default": (()=>__TURBOPACK__default__export__)
});
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
;
const ToolOutput = ({ tool, output })=>{
    let parsedOutput = output;
    // Si el output es un string, intenta convertirlo en JSON válido
    if (typeof output === "string") {
        try {
            // Reemplaza comillas simples por dobles y None por null
            const fixedOutput = output.replace(/None/g, "null").replace(/'/g, '"');
            parsedOutput = JSON.parse(fixedOutput);
            console.log("Output convertido a JSON:", parsedOutput);
        } catch (e) {
            console.error("Error al convertir el output en JSON:", e);
            parsedOutput = {
                error: "No se pudo convertir el output en JSON",
                raw: output
            };
        }
    }
    if (tool === "get_package_timeline") {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "flex-col z-1000 max-h-auto w-full rounded bg-gray-900 text-gray-200 border border-gray-700",
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                            children: [
                                "Nombre en paquete: ",
                                parsedOutput["Dueño del Paquete"]
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/ToolOutput.jsx",
                            lineNumber: 24,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                            children: [
                                "Telefono en paquete: ",
                                parsedOutput["Numero de Telefono"]
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/ToolOutput.jsx",
                            lineNumber: 25,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                            children: [
                                "Tienda donde se compro: ",
                                parsedOutput["Tienda donde se compro el paquete"] || "Tienda Desconocida",
                                "  "
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/ToolOutput.jsx",
                            lineNumber: 26,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/ToolOutput.jsx",
                    lineNumber: 23,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("table", {
                    style: {
                        fontSize: "smaller"
                    },
                    className: "w-full text-sm text-left",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("thead", {
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("tr", {
                                className: "border-b border-gray-600",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("th", {
                                        className: "px-1 py-1",
                                        children: "FECHA"
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/ToolOutput.jsx",
                                        lineNumber: 35,
                                        columnNumber: 15
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("th", {
                                        className: "px-1 py-1",
                                        children: "ESTADO"
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/ToolOutput.jsx",
                                        lineNumber: 36,
                                        columnNumber: 15
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/ToolOutput.jsx",
                                lineNumber: 34,
                                columnNumber: 13
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/src/components/ToolOutput.jsx",
                            lineNumber: 33,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("tbody", {
                            children: parsedOutput.timeline.map((item, idx)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("tr", {
                                    className: "border-b border-gray-800 hover:bg-gray-800",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("td", {
                                            className: "px-2 py-1 whitespace-nowrap",
                                            children: item.dateUser
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/ToolOutput.jsx",
                                            lineNumber: 45,
                                            columnNumber: 17
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("td", {
                                            className: "px-2 py-1 whitespace-nowrap",
                                            children: item.status
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/ToolOutput.jsx",
                                            lineNumber: 46,
                                            columnNumber: 17
                                        }, this)
                                    ]
                                }, idx, true, {
                                    fileName: "[project]/src/components/ToolOutput.jsx",
                                    lineNumber: 41,
                                    columnNumber: 15
                                }, this))
                        }, void 0, false, {
                            fileName: "[project]/src/components/ToolOutput.jsx",
                            lineNumber: 39,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/ToolOutput.jsx",
                    lineNumber: 29,
                    columnNumber: 9
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/ToolOutput.jsx",
            lineNumber: 22,
            columnNumber: 7
        }, this);
    } else {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "max-h-100 max-w-auto bg-gray-900 p-2 text-gray-200 border border-gray-700 text-xs",
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("pre", {
                children: "Vista de Herramienta no disponible aun"
            }, void 0, false, {
                fileName: "[project]/src/components/ToolOutput.jsx",
                lineNumber: 57,
                columnNumber: 9
            }, this)
        }, void 0, false, {
            fileName: "[project]/src/components/ToolOutput.jsx",
            lineNumber: 56,
            columnNumber: 7
        }, this);
    }
    "TURBOPACK unreachable";
};
_c = ToolOutput;
const __TURBOPACK__default__export__ = ToolOutput;
var _c;
__turbopack_context__.k.register(_c, "ToolOutput");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(module, globalThis.$RefreshHelpers$);
}
}}),
"[project]/src/components/AgentTimeline.jsx [app-client] (ecmascript)": ((__turbopack_context__) => {
"use strict";

var { g: global, __dirname, k: __turbopack_refresh__, m: module } = __turbopack_context__;
{
__turbopack_context__.s({
    "default": (()=>__TURBOPACK__default__export__)
});
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$ToolOutput$2e$jsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/components/ToolOutput.jsx [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
;
;
const AgentTimeline = ({ actions, getToolOutput })=>{
    _s();
    const [hoveredItem, setHoveredItem] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const renderTimelineItem = (action, index)=>{
        let label = null;
        let extra = null;
        if (action.type === "function_call") {
            const isHandoff = action.name?.startsWith("transfer_to_");
            if (isHandoff) {
                label = `Handoff: ${action.name.replace("transfer_to_", "")}`;
            } else {
                label = `Tool: ${action.name}`;
                const result = getToolOutput(action.call_id);
                extra = result && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "relative",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "text-sm text-gray-400 mt-1 cursor-pointer hover:text-blue-400",
                            onMouseEnter: ()=>setHoveredItem(index),
                            onMouseLeave: ()=>setHoveredItem(null),
                            children: "Ver resultado"
                        }, void 0, false, {
                            fileName: "[project]/src/components/AgentTimeline.jsx",
                            lineNumber: 24,
                            columnNumber: 13
                        }, this),
                        hoveredItem === index && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "fixed z-1000 max-h-auto mt-1 bg-white dark:bg-gray-800 rounded shadow text-xs text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700 ",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$ToolOutput$2e$jsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                                tool: action.name,
                                output: result
                            }, void 0, false, {
                                fileName: "[project]/src/components/AgentTimeline.jsx",
                                lineNumber: 33,
                                columnNumber: 17
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/src/components/AgentTimeline.jsx",
                            lineNumber: 32,
                            columnNumber: 15
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/AgentTimeline.jsx",
                    lineNumber: 23,
                    columnNumber: 11
                }, this);
            }
        } else if (action.type === "message") {
            label = "Respuesta del Agente";
            extra = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "relative",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "text-sm text-gray-400 mt-1 cursor-pointer hover:text-blue-400",
                        onMouseEnter: ()=>setHoveredItem(index),
                        onMouseLeave: ()=>setHoveredItem(null),
                        children: "Ver respuesta"
                    }, void 0, false, {
                        fileName: "[project]/src/components/AgentTimeline.jsx",
                        lineNumber: 43,
                        columnNumber: 11
                    }, this),
                    hoveredItem === index && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "absolute z-10 mt-1 p-3 w-72 bg-white dark:bg-gray-800 rounded shadow text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700",
                        children: action.content?.[0]?.text
                    }, void 0, false, {
                        fileName: "[project]/src/components/AgentTimeline.jsx",
                        lineNumber: 51,
                        columnNumber: 13
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/AgentTimeline.jsx",
                lineNumber: 42,
                columnNumber: 9
            }, this);
        }
        if (!label) return null;
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("li", {
            className: "relative mb-6 sm:mb-0",
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "flex items-center",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "z-10 flex items-center justify-center w-6 h-6 bg-blue-100 rounded-full ring-0 ring-white dark:bg-blue-900 sm:ring-8 dark:ring-gray-900 shrink-0",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                className: "w-2.5 h-2.5 text-blue-800 dark:text-blue-300",
                                xmlns: "http://www.w3.org/2000/svg",
                                fill: "currentColor",
                                viewBox: "0 0 20 20",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                    d: "M20 4a2 2 0 0 0-2-2h-2V1a1 1 0 0 0-2 0v1h-3V1a1 1 0 0 0-2 0v1H6V1a1 1 0 0 0-2 0v1H2a2 2 0 0 0-2 2v2h20V4Z"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/AgentTimeline.jsx",
                                    lineNumber: 70,
                                    columnNumber: 15
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/AgentTimeline.jsx",
                                lineNumber: 64,
                                columnNumber: 13
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/src/components/AgentTimeline.jsx",
                            lineNumber: 63,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "hidden sm:flex w-full bg-gray-200 h-0.5 dark:bg-gray-700"
                        }, void 0, false, {
                            fileName: "[project]/src/components/AgentTimeline.jsx",
                            lineNumber: 73,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/AgentTimeline.jsx",
                    lineNumber: 62,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "mt-3 sm:pe-8",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h4", {
                            className: "text-base font-semibold text-gray-900 dark:text-white",
                            children: label
                        }, void 0, false, {
                            fileName: "[project]/src/components/AgentTimeline.jsx",
                            lineNumber: 76,
                            columnNumber: 11
                        }, this),
                        extra
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/AgentTimeline.jsx",
                    lineNumber: 75,
                    columnNumber: 9
                }, this)
            ]
        }, index, true, {
            fileName: "[project]/src/components/AgentTimeline.jsx",
            lineNumber: 61,
            columnNumber: 7
        }, this);
    };
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "flex justify-center h-full pt-2",
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("ol", {
            className: "sm:flex",
            children: actions.length ? actions.map(renderTimelineItem) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("li", {
                children: "No hay acciones del agente"
            }, void 0, false, {
                fileName: "[project]/src/components/AgentTimeline.jsx",
                lineNumber: 91,
                columnNumber: 11
            }, this)
        }, void 0, false, {
            fileName: "[project]/src/components/AgentTimeline.jsx",
            lineNumber: 87,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/src/components/AgentTimeline.jsx",
        lineNumber: 86,
        columnNumber: 5
    }, this);
};
_s(AgentTimeline, "1uXs46A7iQzBzVzkML5IJ5VwsdI=");
_c = AgentTimeline;
const __TURBOPACK__default__export__ = AgentTimeline;
var _c;
__turbopack_context__.k.register(_c, "AgentTimeline");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(module, globalThis.$RefreshHelpers$);
}
}}),
"[project]/src/components/AgentResponseModal.jsx [app-client] (ecmascript)": ((__turbopack_context__) => {
"use strict";

var { g: global, __dirname, k: __turbopack_refresh__, m: module } = __turbopack_context__;
{
// Refactor del timeline del agente con hover en respuesta y nuevo layout
__turbopack_context__.s({
    "default": (()=>__TURBOPACK__default__export__)
});
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$AgentTimeline$2e$jsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/components/AgentTimeline.jsx [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
;
;
const AgentResponseModal = ({ ctx, entry, onClose, msg_selected })=>{
    _s();
    const [agentRun, setAgentRun] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    const [hoveredItem, setHoveredItem] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    if (!entry) return null;
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "AgentResponseModal.useEffect": ()=>{
            try {
                console.log("Entry en Modal:", entry, "Context:", ctx);
                setAgentRun(entry.steps_taken);
            } catch (e) {
                console.error("\u274C Error al parsear el contexto:", e);
            }
        }
    }["AgentResponseModal.useEffect"], [
        entry
    ]);
    const agent = entry.responded_by || "General Agent";
    const userEnv = ctx || {};
    const getToolOutput = (call_id)=>{
        const outputObj = agentRun.find((item)=>item.type === "function_call_output" && item.call_id === call_id);
        if (!outputObj) return null;
        try {
            return JSON.stringify(typeof outputObj.output === "string" ? JSON.parse(outputObj.output.replace(/'/g, '"')) : outputObj.output, null, 2);
        } catch (e) {
            return outputObj.output;
        }
    };
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "fixed inset-0 bg-gray/10 backdrop-blur-sm flex items-center justify-center z-50",
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "bg-white dark:bg-gray-800 max-w-[90vw] w-[80vw] rounded-lg max-h-[90vh] h-[90vh] p-6 shadow-xl relative overflow-hidden flex flex-col justify-center items-center",
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h2", {
                    className: "text-xl font-semibold mb-4",
                    children: "Detalles del Proceso"
                }, void 0, false, {
                    fileName: "[project]/src/components/AgentResponseModal.jsx",
                    lineNumber: 44,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                    className: "absolute top-4 right-6 text-gray-500 hover:text-red-600",
                    onClick: onClose,
                    children: "✕"
                }, void 0, false, {
                    fileName: "[project]/src/components/AgentResponseModal.jsx",
                    lineNumber: 45,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "grid grid-cols-[25%_50%_24%] grid-rows-[20%_40%_20%] h-full w-full",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "col-start-1 col-end-2 row-start-1 row-end-2 flex-col text-center",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h2", {
                                    className: "font-semibold text-lg",
                                    children: "Agente que respondió"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/AgentResponseModal.jsx",
                                    lineNumber: 54,
                                    columnNumber: 13
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    className: "text-sm",
                                    children: agent
                                }, void 0, false, {
                                    fileName: "[project]/src/components/AgentResponseModal.jsx",
                                    lineNumber: 55,
                                    columnNumber: 13
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/AgentResponseModal.jsx",
                            lineNumber: 53,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "col-start-1 col-end-4 row-start-2 row-end-3 flex-col",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h2", {
                                    className: "font-semibold text-center text-lg",
                                    children: "Acciones del Agente"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/AgentResponseModal.jsx",
                                    lineNumber: 59,
                                    columnNumber: 13
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$AgentTimeline$2e$jsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                                    actions: agentRun,
                                    getToolOutput: getToolOutput
                                }, void 0, false, {
                                    fileName: "[project]/src/components/AgentResponseModal.jsx",
                                    lineNumber: 62,
                                    columnNumber: 13
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/AgentResponseModal.jsx",
                            lineNumber: 58,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "col-start-1 col-end-2 row-start-3 row-end-4 flex-col",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                    className: "font-semibold text-center p-3",
                                    children: "Contexto del Usuario"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/AgentResponseModal.jsx",
                                    lineNumber: 66,
                                    columnNumber: 13
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("pre", {
                                    className: "bg-gray-100 dark:bg-gray-700 text-xs p-3 rounded whitespace-pre-wrap",
                                    children: JSON.stringify(userEnv, null, 2)
                                }, void 0, false, {
                                    fileName: "[project]/src/components/AgentResponseModal.jsx",
                                    lineNumber: 69,
                                    columnNumber: 13
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/AgentResponseModal.jsx",
                            lineNumber: 65,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/AgentResponseModal.jsx",
                    lineNumber: 52,
                    columnNumber: 9
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/AgentResponseModal.jsx",
            lineNumber: 43,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/src/components/AgentResponseModal.jsx",
        lineNumber: 42,
        columnNumber: 5
    }, this);
};
_s(AgentResponseModal, "iPjUTxLi72bYhUxNtGE6p1cQ+c4=");
_c = AgentResponseModal;
const __TURBOPACK__default__export__ = AgentResponseModal;
var _c;
__turbopack_context__.k.register(_c, "AgentResponseModal");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(module, globalThis.$RefreshHelpers$);
}
}}),
"[project]/src/components/Chat.jsx [app-client] (ecmascript)": ((__turbopack_context__) => {
"use strict";

var { g: global, __dirname, k: __turbopack_refresh__, m: module } = __turbopack_context__;
{
__turbopack_context__.s({
    "default": (()=>__TURBOPACK__default__export__)
});
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$AgentResponseModal$2e$jsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/components/AgentResponseModal.jsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$services$2f$ManagerUI_service$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/services/ManagerUI_service.js [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
;
;
;
const Chat = ({ userId, style })=>{
    _s();
    const containerRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const [selectedEntry, setSelectedEntry] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [selectedContext, setSelectedContext] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [showModal, setShowModal] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [msg_idx, setMsg_idx] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [message_range, setMessage_range] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(10);
    const [session_history, set_Session_history] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    const format_input_items = (input_items)=>{
        const result = [];
        let i = 0;
        while(i < input_items.length){
            if (input_items[i].role === "user") {
                const user_message = input_items[i];
                const steps_taken = [];
                let agent_message = null;
                let responded_by = "General Agent";
                let j = i + 1;
                // Busca hasta el siguiente mensaje del usuario
                while(j < input_items.length){
                    const item = input_items[j];
                    if (item.role === "user") {
                        break;
                    }
                    if (item.output && item.type === "function_call_output") {
                        try {
                            let output = JSON.parse(item.output);
                            if (output.assistant) {
                                responded_by = output.assistant;
                            }
                        } catch  {}
                    }
                    // Mensaje del agente
                    if (item.role === "assistant" && item.type === "message") {
                        agent_message = item;
                    } else {
                        steps_taken.push(item);
                    }
                    j++;
                }
                if (agent_message) {
                    result.push({
                        user_message,
                        agent_message,
                        steps_taken,
                        responded_by
                    });
                    i = j;
                } else {
                    // Si no hay respuesta del agente, solo avanza
                    i++;
                }
            } else {
                i++;
            }
        }
        return result;
    };
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "Chat.useEffect": ()=>{
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$services$2f$ManagerUI_service$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fetchUserHistory"])(userId, message_range).then({
                "Chat.useEffect": (data)=>{
                    let session_history = [];
                    data.forEach({
                        "Chat.useEffect": (session)=>{
                            let raw_entry = session.contexto;
                            let entry = JSON.parse(raw_entry);
                            let input_items = format_input_items(entry.input_items);
                            session_history.push({
                                id: session.id,
                                context: entry.context,
                                fecha: session.fecha,
                                input_items
                            });
                        }
                    }["Chat.useEffect"]);
                    set_Session_history(session_history.reverse());
                }
            }["Chat.useEffect"]);
        }
    }["Chat.useEffect"], [
        userId,
        message_range
    ]);
    const handleAgentClick = (ctx, entry, idx)=>{
        setSelectedContext(ctx);
        setSelectedEntry(entry);
        setMsg_idx(idx);
        setShowModal(true);
    };
    const loadMoreMessages = async ()=>{
        if (session_history.length === 0) return;
        const first_id = session_history[0].id;
        const container = containerRef.current;
        const previousScrollTop = container.scrollTop;
        const previousHeight = container.scrollHeight;
        const newMessages = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$services$2f$ManagerUI_service$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fetchUserHistory"])(userId, message_range, first_id);
        if (newMessages.length > 0) {
            const reversedNew = newMessages.reverse();
            set_Session_history((prev)=>[
                    ...reversedNew,
                    ...prev
                ]);
            // Espera a que el DOM se actualice
            requestAnimationFrame(()=>{
                const newHeight = container.scrollHeight;
                const delta = newHeight - previousHeight;
                container.scrollTop = previousScrollTop + delta;
            });
        }
    };
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "Chat.useEffect": ()=>{
            const container = containerRef.current;
            if (!container) return;
            const handleScroll = {
                "Chat.useEffect.handleScroll": ()=>{
                    if (container.scrollTop === 0) {
                        loadMoreMessages();
                    }
                }
            }["Chat.useEffect.handleScroll"];
            container.addEventListener("scroll", handleScroll);
            return ({
                "Chat.useEffect": ()=>container.removeEventListener("scroll", handleScroll)
            })["Chat.useEffect"];
        }
    }["Chat.useEffect"], [
        session_history
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "Chat.useEffect": ()=>{
            if (session_history.length === 0) return;
            const container = containerRef.current;
            // Solo hacer scroll al fondo si el scroll ya estaba abajo o es primera carga
            const isInitialLoad = container.scrollTop === 0 || container.scrollTop === container.scrollHeight;
            if (isInitialLoad) {
                setTimeout({
                    "Chat.useEffect": ()=>{
                        container.scrollTop = container.scrollHeight;
                    }
                }["Chat.useEffect"], 0);
            }
        }
    }["Chat.useEffect"], [
        session_history.length === message_range
    ]); // se ejecuta solo cuando cambia el lote inicial
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        ref: containerRef,
        style: {
            ...style,
            overflowY: "auto"
        },
        className: "p-4 flex flex-col gap-4",
        children: [
            session_history.map((entry, idx)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "flex flex-col gap-2",
                    children: entry.input_items.map((item, itemIdx)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex items-start gap-2.5",
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "flex flex-col w-full max-w-[320px] leading-1.5 p-4 rounded-e-xl rounded-es-xl",
                                        style: {
                                            backgroundColor: "#ac302c"
                                        },
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "flex items-center justify-between",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                        className: "text-sm font-semibold text-gray-900 dark:text-white",
                                                        children: "Usuario"
                                                    }, void 0, false, {
                                                        fileName: "[project]/src/components/Chat.jsx",
                                                        lineNumber: 168,
                                                        columnNumber: 21
                                                    }, this),
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                        className: "text-xs",
                                                        children: entry.fecha ? new Date(new Date(entry.fecha).getTime() - 6 * 60 * 60 * 1000).toLocaleTimeString() : ""
                                                    }, void 0, false, {
                                                        fileName: "[project]/src/components/Chat.jsx",
                                                        lineNumber: 171,
                                                        columnNumber: 21
                                                    }, this)
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/src/components/Chat.jsx",
                                                lineNumber: 167,
                                                columnNumber: 19
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                                className: "text-sm text-gray-900 dark:text-white mt-2",
                                                children: item.user_message?.content
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/Chat.jsx",
                                                lineNumber: 179,
                                                columnNumber: 19
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/src/components/Chat.jsx",
                                        lineNumber: 163,
                                        columnNumber: 17
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/src/components/Chat.jsx",
                                    lineNumber: 162,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex items-start justify-end gap-3 cursor-pointer",
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "flex flex-col w-full max-w-[320px] leading-1.5 p-4 rounded-s-xl rounded-ee-xl mr-6",
                                        style: {
                                            backgroundColor: "#013544"
                                        },
                                        onClick: ()=>handleAgentClick(entry.context, item, idx),
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "flex items-center justify-between ",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                        className: "text-sm font-semibold text-gray-900 dark:text-white",
                                                        children: item.responded_by || "Agente"
                                                    }, void 0, false, {
                                                        fileName: "[project]/src/components/Chat.jsx",
                                                        lineNumber: 193,
                                                        columnNumber: 21
                                                    }, this),
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                        className: "text-xs text-gray-500 dark:text-gray-300",
                                                        children: entry.fecha ? new Date(new Date(entry.fecha).getTime() - 6 * 60 * 60 * 1000).toLocaleTimeString() : ""
                                                    }, void 0, false, {
                                                        fileName: "[project]/src/components/Chat.jsx",
                                                        lineNumber: 196,
                                                        columnNumber: 21
                                                    }, this)
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/src/components/Chat.jsx",
                                                lineNumber: 192,
                                                columnNumber: 19
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                                className: "text-sm text-gray-900 dark:text-white mt-2",
                                                children: Array.isArray(item.agent_message?.content) ? JSON.parse(item.agent_message.content[0].text).response : ""
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/Chat.jsx",
                                                lineNumber: 204,
                                                columnNumber: 19
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/src/components/Chat.jsx",
                                        lineNumber: 187,
                                        columnNumber: 17
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/src/components/Chat.jsx",
                                    lineNumber: 186,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, itemIdx, true, {
                            fileName: "[project]/src/components/Chat.jsx",
                            lineNumber: 160,
                            columnNumber: 13
                        }, this))
                }, entry.id || idx, false, {
                    fileName: "[project]/src/components/Chat.jsx",
                    lineNumber: 158,
                    columnNumber: 9
                }, this)),
            showModal && selectedEntry && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$AgentResponseModal$2e$jsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                ctx: selectedContext,
                msg_selected: msg_idx,
                entry: selectedEntry,
                show: showModal,
                onClose: ()=>setShowModal(false),
                style: {
                    display: "flex",
                    alignSelf: "center",
                    justifyContent: "center"
                }
            }, void 0, false, {
                fileName: "[project]/src/components/Chat.jsx",
                lineNumber: 217,
                columnNumber: 9
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/src/components/Chat.jsx",
        lineNumber: 152,
        columnNumber: 5
    }, this);
};
_s(Chat, "ViodKydgFTF4DScwDY2W30SIoU0=");
_c = Chat;
const __TURBOPACK__default__export__ = Chat;
var _c;
__turbopack_context__.k.register(_c, "Chat");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(module, globalThis.$RefreshHelpers$);
}
}}),
"[project]/src/app/ManagerUI/page.jsx [app-client] (ecmascript)": ((__turbopack_context__) => {
"use strict";

var { g: global, __dirname, k: __turbopack_refresh__, m: module } = __turbopack_context__;
{
__turbopack_context__.s({
    "default": (()=>ManagerUIPage)
});
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$ConversationsTab$2e$jsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/components/ConversationsTab.jsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$Chat$2e$jsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/components/Chat.jsx [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
"use client";
;
;
;
function ManagerUIPage() {
    _s();
    const [selectedUserId, setSelectedUserId] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        style: {
            display: "grid",
            gridTemplateRows: "50px 1fr",
            gridTemplateColumns: "15% 1fr",
            height: "100vh",
            width: "100vw",
            minHeight: 0
        },
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                style: {
                    gridRow: "2",
                    gridColumn: "1",
                    backgroundColor: "#000b24ff",
                    display: "flex",
                    flexDirection: "column",
                    textAlign: "center"
                },
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                            children: "Chats"
                        }, void 0, false, {
                            fileName: "[project]/src/app/ManagerUI/page.jsx",
                            lineNumber: 32,
                            columnNumber: 11
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/src/app/ManagerUI/page.jsx",
                        lineNumber: 31,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                            children: "Prompts"
                        }, void 0, false, {
                            fileName: "[project]/src/app/ManagerUI/page.jsx",
                            lineNumber: 35,
                            columnNumber: 11
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/src/app/ManagerUI/page.jsx",
                        lineNumber: 34,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/app/ManagerUI/page.jsx",
                lineNumber: 21,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                style: {
                    gridRow: "1",
                    gridColumn: "1/ span 2",
                    backgroundColor: "#000b24f9",
                    display: "flex",
                    flexDirection: "row",
                    justifyContent: "space-between",
                    alignItems: "center",
                    height: "100%",
                    alignSelf: "start",
                    borderRight: "2px solid #ac302c",
                    borderBottom: "2px solid #ac302c",
                    position: "static",
                    zIndex: 20
                },
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        style: {
                            height: "100%",
                            display: "flex",
                            justifyItems: "center",
                            alignItems: "center"
                        },
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                            src: "SAC-manager-Title.png",
                            alt: "Logo Moovin",
                            style: {
                                height: "60%",
                                paddingLeft: 15
                            }
                        }, void 0, false, {
                            fileName: "[project]/src/app/ManagerUI/page.jsx",
                            lineNumber: 64,
                            columnNumber: 11
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/src/app/ManagerUI/page.jsx",
                        lineNumber: 56,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        style: {
                            height: "75%",
                            backgroundColor: "white",
                            borderRadius: "5px",
                            margin: "0.75rem"
                        },
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                            src: "moovin_logo.png",
                            alt: "Logo Moovin",
                            style: {
                                height: "100%",
                                padding: 8
                            }
                        }, void 0, false, {
                            fileName: "[project]/src/app/ManagerUI/page.jsx",
                            lineNumber: 82,
                            columnNumber: 11
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/src/app/ManagerUI/page.jsx",
                        lineNumber: 74,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/app/ManagerUI/page.jsx",
                lineNumber: 39,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                style: {
                    gridRow: "2",
                    gridColumn: "2",
                    display: "grid",
                    gridTemplateColumns: "1fr 3fr"
                },
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        style: {
                            gridColumn: "1",
                            height: "100%",
                            borderRight: "2px solid #ac302c"
                        },
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$ConversationsTab$2e$jsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                            onSelectUser: setSelectedUserId,
                            selectedUserId: selectedUserId
                        }, void 0, false, {
                            fileName: "[project]/src/app/ManagerUI/page.jsx",
                            lineNumber: 107,
                            columnNumber: 11
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/src/app/ManagerUI/page.jsx",
                        lineNumber: 100,
                        columnNumber: 9
                    }, this),
                    selectedUserId ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$Chat$2e$jsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                        userId: selectedUserId,
                        style: {
                            gridColumn: "2",
                            height: "100%",
                            width: "100%",
                            display: "flex",
                            backgroundColor: "#ffffffff",
                            flexDirection: "column"
                        }
                    }, void 0, false, {
                        fileName: "[project]/src/app/ManagerUI/page.jsx",
                        lineNumber: 114,
                        columnNumber: 11
                    }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        style: {
                            gridRow: "2",
                            backgroundColor: "#ebe4eb",
                            gridColumn: "2",
                            flex: 1,
                            padding: 20,
                            justifyContent: "center",
                            alignItems: "center",
                            display: "flex",
                            color: "#00255a",
                            fontSize: "larger",
                            fontWeight: "bold"
                        },
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                            children: "Selecciona una conversación"
                        }, void 0, false, {
                            fileName: "[project]/src/app/ManagerUI/page.jsx",
                            lineNumber: 141,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/src/app/ManagerUI/page.jsx",
                        lineNumber: 126,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/app/ManagerUI/page.jsx",
                lineNumber: 92,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/src/app/ManagerUI/page.jsx",
        lineNumber: 10,
        columnNumber: 5
    }, this);
}
_s(ManagerUIPage, "XgWC7K+UW7JnvJKTIvHgHgmCH6M=");
_c = ManagerUIPage;
var _c;
__turbopack_context__.k.register(_c, "ManagerUIPage");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(module, globalThis.$RefreshHelpers$);
}
}}),
}]);

//# sourceMappingURL=src_4f4cdc60._.js.map