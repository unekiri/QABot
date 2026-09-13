# QABot

ドキュメントを学習し、質問に回答するチャットボットシステム

## システム構成図

<img width="718" height="411" alt="QABotのシステム構成図" src="https://github.com/user-attachments/assets/8c37c4a0-70ae-4784-b6da-5184b36d7bd3" />

## 起動

初回のみ、Ollamaへ回答モデルを登録します。

```powershell
ollama pull gemma3:1b
```

次のスクリプトを実行し、12文字以上のパスワードを入力します。パスワードはコマンド履歴、リポジトリ、コンテナ環境変数へ保存されません。

```powershell
.\scripts\start.ps1
```

ブラウザで `http://localhost:8080` を開きます。既定のユーザー名は `qabot` です。変更する場合は `-User` を指定します。

```powershell
.\scripts\start.ps1 -User local-admin
```

APIとChromaDBはDocker内部ネットワーク限定です。埋め込みモデルはイメージ構築時に取得され、実行時はオフラインモードで読み込まれます。
