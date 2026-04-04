import React, { useState, useEffect } from 'react';
import { getShopItems, buyItem } from '../api';

const CATEGORIES = [
  { key: null, label: '전체' },
  { key: 'animal', label: '동물' },
  { key: 'tree', label: '나무/꽃' },
  { key: 'building', label: '건물' },
];

export default function ShopPanel({ userHearts, userLevel, onClose, onRefresh, showToast }) {
  const [items, setItems] = useState([]);
  const [category, setCategory] = useState(null);

  const loadItems = async (cat) => {
    try {
      const res = await getShopItems(cat);
      setItems(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => { loadItems(category); }, [category]);

  const handleBuy = async (item) => {
    if (item.owned) {
      showToast('이미 소유한 아이템이에요!');
      return;
    }
    if (userLevel < item.unlock_level) {
      showToast(`레벨 ${item.unlock_level} 이상 필요해요 (현재 Lv.${userLevel})`);
      return;
    }
    if (userHearts < item.price) {
      showToast(`하트가 부족해요! (필요: ${item.price}, 보유: ${userHearts})`);
      return;
    }
    if (!window.confirm(`'${item.name}'을(를) ${item.price} 하트로 구매할까요?`)) return;

    try {
      const res = await buyItem(item.id);
      showToast(res.data.message);
      onRefresh();
      loadItems(category);
    } catch (err) {
      showToast(err.response?.data?.detail || '구매 실패');
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-title">&#128722; 상점</div>

        <div style={{ textAlign: 'center', marginBottom: '12px', fontSize: '14px', color: '#e74c3c' }}>
          &#10084; {userHearts} 보유
        </div>

        <div className="shop-tabs">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.key || 'all'}
              className={`shop-tab ${category === cat.key ? 'active' : ''}`}
              onClick={() => setCategory(cat.key)}
            >
              {cat.label}
            </button>
          ))}
        </div>

        <div className="shop-grid">
          {items.map((item) => {
            const locked = userLevel < item.unlock_level;
            return (
              <div
                key={item.id}
                className={`shop-card ${item.owned ? 'owned' : ''}`}
                onClick={() => !locked && handleBuy(item)}
                style={locked ? { opacity: 0.35, cursor: 'not-allowed' } : {}}
              >
                <span className={`rarity-badge rarity-${item.rarity}`}>{item.rarity}</span>
                <span className="emoji">{locked ? '🔒' : item.emoji}</span>
                <div className="name">{item.name}</div>
                <div className="price">
                  {item.owned ? '보유중' : `❤ ${item.price}`}
                </div>
                {locked && (
                  <div style={{ fontSize: '9px', color: '#999' }}>Lv.{item.unlock_level}</div>
                )}
              </div>
            );
          })}
        </div>

        <button className="cancel-btn" onClick={onClose} style={{ marginTop: '16px' }}>닫기</button>
      </div>
    </div>
  );
}
