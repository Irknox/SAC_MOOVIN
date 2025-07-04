const Chat = ({ history, userId, style }) => {
  const userHistory = history.filter(entry => entry.user_id === userId);

  return (
    <div style={style}>
      <div>
        {userHistory.map((entry, idx) => (
          <div key={idx} style={{ marginBottom: 10 }}>
            <div style={{color: "black"}}>
              <strong style={{color: "green"}}>Usuario:</strong> {entry.mensaje_entrante}
            </div>
            <div style={{color: "black"}}>
              <strong style={{color: "blue"}}>Agente:</strong> {entry.mensaje_saliente}
            </div>
            <div style={{ fontSize: 10, color: "black" }}>
              {new Date(new Date(entry.fecha).getTime() - 6 * 60 * 60 * 1000).toLocaleString()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Chat;