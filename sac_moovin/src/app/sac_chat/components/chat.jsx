"use client";

import { useState } from 'react';
import { sendMessage } from '../interaction_service'; 

const styles = {
  chatContainer: {
    width: '100%',
    maxWidth: '400px',
    margin: '0 auto',
    border: '1px solid #ccc',
    borderRadius: '8px',
    padding: '10px',
    display: 'flex',
    flexDirection: 'column',
    height: '600px',
  },
  messageList: {
    flex: 1,
    overflowY: 'auto',
    marginBottom: '10px',
    padding: '5px',
  },
  userMessage: {
    textAlign: 'right',
    margin: '5px 0',
    color: 'white',
  },
  botMessage: {
    textAlign: 'left',
    margin: '5px 0',
    color: 'orange',
  },
  inputContainer: {
    display: 'flex',
    gap: '5px',
  },
  input: {
    flex: 1,
    padding: '5px',
  },
  button: {
    padding: '5px 10px',
  },
};

const Chat = () => {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSendMessage = async () => {
    if (inputText.trim() !== '') {
      const userMessage = { sender: 'user', text: inputText };
      setMessages(prev => [...prev, userMessage]);
      setInputText('');
      setLoading(true);
      try {
        console.log('Sending message to server:', userMessage.text);
        const botResponse = await sendMessage(userMessage.text);
        console.log('Received response from server:', botResponse);
        
        setMessages(prev => [...prev, { sender: 'bot', text: botResponse }]);
      } catch (error) {
        setMessages(prev => [...prev, { sender: 'bot', text: 'Error al obtener respuesta del servidor.' }]);
      }
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') handleSendMessage();
  };

  return (
    <div style={styles.chatContainer}>
      <div style={styles.messageList}>
        {messages.map((msg, index) => (
          <div key={index} style={msg.sender === 'user' ? styles.userMessage : styles.botMessage}>
            <strong>{msg.sender === 'user' ? 'Tú' : 'Bot'}:</strong> {msg.text}
          </div>
        ))}
        {loading && (
          <div style={styles.botMessage}>
            <strong>Bot:</strong> <em>Escribiendo...</em>
          </div>
        )}
      </div>
      <div style={styles.inputContainer}>
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Escribe tu mensaje..."
          style={styles.input}
          disabled={loading}
        />
        <button onClick={handleSendMessage} style={styles.button} disabled={loading}>Enviar</button>
      </div>
    </div>
  );
};

export default Chat;
