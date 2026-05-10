import axios from 'axios';

const API = axios.create({ baseURL: 'http://127.0.0.1:8000/api' });

// 유저
export const getUser = () => API.get('/user');

// 습관
export const getHabits = () => API.get('/habits');
export const createHabit = (data) => API.post('/habits', data);
export const completeHabit = (id) => API.post(`/habits/${id}/complete`);
export const deleteHabit = (id) => API.delete(`/habits/${id}`);

// 나무
export const getTrees = () => API.get('/trees');
export const harvestTree = (id) => API.post(`/trees/${id}/harvest`);
export const moveTree = (id, grid_x, grid_y) =>
  API.patch(`/trees/${id}/position`, { grid_x, grid_y });

// 상점
export const getShopItems = (category) =>
  API.get('/shop', { params: category ? { category } : {} });
export const buyItem = (id) => API.post(`/shop/${id}/buy`);

// 배치
export const getPlacedItems = () => API.get('/placed-items');
export const placeItem = (data) => API.post('/placed-items', data);
export const removePlacedItem = (id) => API.delete(`/placed-items/${id}`);

// 캘린더
export const getCalendarMonth = (year, month) =>
  API.get('/calendar/month', { params: { year, month } });
export const getCalendarDay = (date) =>
  API.get('/calendar/day', { params: { date } });

export default API;
