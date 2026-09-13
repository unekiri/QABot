# QABot

ドキュメントを学習し、質問に回答するチャットボットシステム

## システム構成図
![image](https://github.com/user-attachments/assets/e25d893c-2d9f-41df-9bcb-ce148c33e02f)

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
