# X (Twitter) Developer Account 申請用テキスト

> 2026-05-30 作成。 https://developer.x.com/ で Free tier アカウント申請する際に必要な「Tell us about your use case」「How will you use Twitter data and the Twitter API」等の欄に貼り付ける説明文。

## ⚠ X Developer 申請の注意点

- X (旧 Twitter) は **英語申請を強く推奨** (日本語のみだと審査落ちのリスク)
- 各説明欄は **最低 100-200 文字、推奨 300+ 文字**
- **DM やフォロー自動化は明確に否定**する (これらは禁止行為扱い)
- **投稿頻度の数値**を明示 (1日6回、月180本)
- **無料枠 (月 500 投稿) 内**であることを記載
- **自社サービスへの誘導** が目的と書く (= 第三者リサーチではない)

---

## Q1: "In your words"
*(What are you doing with the developer account?)*

### 英語版 (推奨、約 600 文字)
```
I'm building a periodic content distribution bot for my own service "TOI-Suite" (https://toi-suite.vercel.app/), which provides a 6-axis self-diagnostic quiz and "200 questions" curated through the lens of samurai philosophy for mature adults. The bot will post tweets via GitHub Actions cron at six fixed times per day (every 4 hours), totaling approximately 180 tweets per month. Each tweet contains a brief Japanese message and a link to one of our own URLs (the diagnostic page, audio drama episodes, or upcoming PWA utility apps). The purpose is to maintain consistent visibility for the service among Japanese-speaking audiences interested in psychology, classical philosophy, and personal development. The bot does not interact with other users: no replies, no direct messages, no following, no liking, no retweeting. It only publishes original tweets from a pre-defined rotation of 10 templates. All posting stays well within the Free tier limit of 500 tweets per month.
```

### 日本語版 (約 250 文字)
```
自社サービス「TOI-Suite」(https://toi-suite.vercel.app/) の定期紹介投稿用 bot を構築しています。 心理学・古典・現代思想を侍の哲学で再編した「200の問い」と 6 軸自己診断を、 GitHub Actions cron で 1 日 6 回 (4 時間ごと、 月 180 投稿) 自動投稿します。 投稿内容は自社 URL への誘導のみで、 リプライ・DM・フォロー・いいね・リツイートなど他ユーザーとの対話操作は一切行いません。 10 種類の固定テンプレからランダムに 1 件選んで投稿するシンプルな構成で、 X API 無料枠 (月 500 投稿) の範囲内です。
```

---

## Q2: "Are you planning to analyze Twitter data?"

### 英語版 (約 250 文字)
```
No. This bot is purely for posting (write-only). It does not read tweets, do not collect data on other users, does not analyze trends, and does not perform any form of data harvesting. The only API endpoint used is POST /2/tweets to publish our own pre-written promotional messages.
```

### 日本語版 (約 100 文字)
```
データ分析は一切行いません。 用途は自社サービスの定期投稿のみで、 POST /2/tweets エンドポイントしか使用しません。 他ユーザーの投稿取得、 トレンド分析、 データ収集は行いません。
```

---

## Q3: "Will your App use Tweet, Retweet, Like, Follow, or Direct Message functionality?"

### 英語版 (約 200 文字)
```
Only the Tweet (POST) functionality. The bot publishes original tweets from a pre-defined template rotation. It does not retweet, like, reply, follow, or send direct messages. There are no interactions with other users at all.
```

### 日本語版 (約 100 文字)
```
ツイート投稿 (POST) 機能のみ使用します。 リツイート、 いいね、 リプライ、 フォロー、 DM は一切行いません。 他ユーザーとの対話は完全になしです。
```

---

## Q4: "Do you plan to display Tweets or aggregate data about Twitter content outside Twitter?"

### 英語版 (約 200 文字)
```
No. The bot does not display any tweets externally, does not aggregate data, does not embed tweets on our website, and does not republish Twitter content anywhere. The bot only publishes our own tweets and that's the entire scope.
```

### 日本語版 (約 100 文字)
```
いいえ。 X のコンテンツを外部に表示・集約・転載することはありません。 本 bot は自社の投稿を行うのみで、 他のすべての機能は範囲外です。
```

---

## Q5: "Will your product, service, or analysis make Twitter content or derived information available to a government entity?"

```
No.
```

---

## 申請の流れ (推奨手順)

1. https://developer.x.com/en/portal/petition/essential/basic-info にアクセス
2. X アカウント (@uchy0307 想定) でログイン
3. 「Sign up for Free Account」を選択
4. 上記 Q1〜Q5 の英語版を **そのままコピペ**
5. (日本語版は補助として残しておく、 審査の都合で日本語申請になった場合用)
6. メールアドレス確認
7. **即承認 or 数時間〜数日の審査** (Free tier なら通常即時)
8. 承認後、Project + App を作成
9. User authentication settings → "Read and Write" + "Web App, Automated App or Bot" を選択
10. Keys and tokens で 4 種 generate
11. GitHub Secrets 設定
12. workflow_dispatch でテスト発火

## ⚠ 申請通過率を上げるコツ

- 英語で書く (機械翻訳バレでも OK、 シンプルな英語で)
- 「Read-only / Write-only」を明確化 (本 bot は Write-only)
- 「No interactions with other users」を強調
- 投稿数を具体的に書く (180/month、 Free 枠 500 の範囲内)
- 自社サービス URL を明示 (透明性アピール)
- ハッシュタグスパム・大量フォロー目的の bot ではないと明確化

## 注意: 申請時のキーワード回避

- ❌ "marketing automation" (スパム認定リスク)
- ❌ "growth hacking" (ガイドライン違反扱い)
- ❌ "follow back bot" (即拒否)
- ❌ "engagement bot" (即拒否)
- ✅ "content distribution for our own service"
- ✅ "periodic notification"
- ✅ "scheduled announcement"
