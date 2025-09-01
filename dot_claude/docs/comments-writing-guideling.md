**コードコメント作成ガイドライン**

## **書いてはいけないコメント**

### 1. 会話履歴・変更経緯への言及
```javascript
// ❌ ここのAPIエンドポイントを変更
// ❌ 上記の要求に従ってvalidationを追加
// ❌ 先ほどの実装から改善
const apiUrl = 'https://api.example.com/v2';
```

### 2. 自明な処理の過剰説明
```javascript
// ❌ 変数userNameに文字列を代入する
const userName = "John";

// ❌ forループで配列を繰り返し処理
for (let i = 0; i < users.length; i++) {
```

### 3. 抽象的すぎる説明
```javascript
// ❌ データを処理する
// ❌ 処理を実行
const result = transform(data);
```

## **書くべきコメント**

### 1. ビジネス要件・制約
```javascript
// ✅ 金融規制により取引履歴は7年間保持が必要
const TRANSACTION_RETENTION_YEARS = 7;

// ✅ PCI DSS準拠のためカード番号は暗号化保存
const encryptedCard = encrypt(cardNumber);
```

### 2. 技術的判断の根拠
```javascript
// ✅ レスポンス時間500ms以下維持のためキャッシュ利用
const result = cache.get(key) || await fetchFromAPI();

// ✅ 10万件超データではページネーション必須（メモリ制限対応）
const PAGINATION_SIZE = 1000;
```

### 3. セキュリティ・パフォーマンス考慮
```javascript
// ✅ XSS防止のためユーザー入力をサニタイズ
const sanitized = DOMPurify.sanitize(input);

// ✅ デバウンス処理でAPI呼び出し制限（Rate Limit対策）
const debouncedSearch = debounce(searchAPI, 300);
```

### 4. エラー処理の想定ケース
```javascript
try {
  const data = await externalAPI();
} catch (error) {
  // ✅ ネットワーク障害・タイムアウト・API制限エラーを想定
  // 5分後に自動リトライ、3回失敗で管理者通知
  handleAPIError(error);
}
```

### 5. 将来の拡張性・保守性
```javascript
// ✅ 新しい決済方法追加時はここにcase文を追加
switch (paymentMethod) {
  case 'credit_card':
  case 'bank_transfer':
  // 将来: 'digital_wallet', 'cryptocurrency' 等
}

// ✅ 外部API依存: Stripe v2023-10-16（破壊的変更注意）
const stripe = new Stripe(key, { apiVersion: '2023-10-16' });
```

### 6. 複雑な状態・アルゴリズム
```javascript
// ✅ 楽観的更新: UI即座更新後、API失敗時はロールバック
const optimisticUpdate = (data) => {
  updateUI(data);
  api.save(data).catch(() => rollbackUI(oldData));
};

// ✅ Luhnアルゴリズムでクレジットカード番号検証
const isValidCard = (number) => {
  // 偶数位置の数字を2倍し、9超過時は各桁合計
```

**コメントの原則**：
- **なぜ**その実装が必要かを説明する
- ビジネス要件・技術制約との関連を明記する
- 将来の保守者が迷わない判断材料を提供する
- パフォーマンス・セキュリティへの配慮を明記する
