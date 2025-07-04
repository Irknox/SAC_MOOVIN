import axios from "axios";

const API_URL = "http://localhost:8000/ManagerUI";

export const fetchAgentHistory = async () => {
  try {
    const response = await axios.post(API_URL);
    return response.data.history;
  } catch (error) {
    console.error("Error fetching agent history:", error);
    throw error;
  }
};