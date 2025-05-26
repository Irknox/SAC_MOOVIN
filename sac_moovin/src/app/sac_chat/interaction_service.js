import axios from 'axios';

const API_URL = 'http://127.0.0.1:8000/ask';

export async function sendMessage(message) {
  try {
    const response = await axios.post(API_URL, { message });
    return response.data.model_response||"no response from server";
  } catch (error) {
    console.error('Error sending message:', error);
    throw error;
  }
}