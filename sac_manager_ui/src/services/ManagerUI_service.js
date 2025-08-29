import axios from "axios";

const API_URL = "/SilverAI/Manager/Handler";
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
    //console.log("Valor de la respuesta a la sessiones desde el serivico:",response.data.history);

    return response.data.history;
  } catch (error) {
    console.error("Error fetching agent history:", error);
    throw error;
  }
};

export const fetchPrompt = async (prompt_type) => {
  try {
    const response = await axios.post(API_URL, {
      request: "Prompt",
      request_body: { type: prompt_type },
    });
    console.log("response.data es:", response.data);

    return response.data;
  } catch (error) {
    console.error("Error fetching prompt:", error);
    throw error;
  }
};

export const updatePrompt = async (prompt_owner, prompt) => {
  try {
    const response = await axios.post(API_URL, {
      request: "Prompt_update",
      request_body: { updated_prompt: prompt, prompt_owner },
    });
    return response.data;
  } catch (error) {
    console.error("Error fetching prompt:", error);
    throw error;
  }
};
