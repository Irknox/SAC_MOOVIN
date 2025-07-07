const Chat = ({ history, userId, style }) => {
  const userHistory = history.filter(entry => entry.user_id === userId);
  console.log("📝 Historial de usuario:", userHistory);
  return (
    <div style={style} className="p-4 space-y-4">
      {userHistory.map((entry, idx) => (
        <div key={idx} className="flex flex-col gap-2">
          {/* Mensaje del Usuario */}
          {entry.mensaje_entrante && (
            <div className="flex items-start gap-2.5">
              <div className="flex flex-col w-full max-w-[320px] leading-1.5 p-4 bg-gray-100 rounded-e-xl rounded-es-xl dark:bg-gray-700">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-gray-900 dark:text-white">Usuario</span>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {new Date(new Date(entry.fecha).getTime() - 6 * 60 * 60 * 1000).toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-sm text-gray-900 dark:text-white mt-2">{entry.mensaje_entrante}</p>
              </div>
            </div>
          )}

          {/* Mensaje del Agente */}
          {entry.mensaje_saliente && (
            <div className="flex items-start justify-end gap-3 ">
              <div className="flex flex-col w-full max-w-[320px] leading-1.5 p-4 bg-blue-700 rounded-s-xl rounded-ee-xl dark:bg-blue-700 mr-6">
                <div className="flex items-center justify-between ">
                  <span className="text-sm font-semibold text-gray-900 dark:text-white">Agente</span>
                  <span className="text-xs text-gray-500 dark:text-gray-300">
                    {new Date(new Date(entry.fecha).getTime() - 6 * 60 * 60 * 1000).toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-sm text-gray-900 dark:text-white mt-2">{entry.mensaje_saliente}</p>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default Chat;
