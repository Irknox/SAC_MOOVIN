import axios from "axios";

const API_URL = "http://localhost:8000/ManagerUI";

export const fetchHistoryPreview = async () => {
  try {
    const response = await axios.post(API_URL, {
      request: "UsersLastMessages",
    });
    return response.data.history;
  } catch (error) {
    console.error("Error fetching agent history:", error);
    throw error;
  }
};

export const fetchUserHistory = async (
  user_id,
  range_requested,
  last_id = null
) => {
  try {
    const request_body = {
      user: user_id,
      range: range_requested,
    };

    if (last_id !== null) {
      request_body.last_id = last_id;
    }

    const response = await axios.post(API_URL, {
      request: "UserHistory",
      request_body,
    });
    console.log("Response history", response.data.history);

    return response.data.history;
  } catch (error) {
    console.error("Error fetching agent history:", error);
    throw error;
  }
};
