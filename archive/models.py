import torch
import torch.nn as nn
import math
from torch.nn import functional as F
import torchvision.models as models

N_IN_CHANNELS = 3

class Autoencoder(nn.Module):
    def __init__(self, n_out_channels1=4, n_out_channels2=4, n_out_channels3=1, \
                kernel_size1=5, kernel_size2=5, kernel_size3=5):
        super(Autoencoder, self).__init__()
        self.encoder = nn.Sequential(
            nn.Conv2d(N_IN_CHANNELS, out_channels=n_out_channels1, kernel_size=kernel_size1, stride=2, padding=2), 
            nn.ReLU(),
            nn.MaxPool2d(4, stride=2, padding=1),

            nn.Conv2d(in_channels=n_out_channels1, out_channels=n_out_channels2, kernel_size=kernel_size2, stride=2, padding=2),
            nn.ReLU(),
            nn.MaxPool2d(5, stride=1, padding=2),

            nn.Conv2d(in_channels=n_out_channels2, out_channels=n_out_channels3, kernel_size=kernel_size3, stride=3, padding=2),
            nn.MaxPool2d(5, stride=1, padding=2),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.Upsample(scale_factor=3),
            nn.Conv2d(n_out_channels3, n_out_channels2, kernel_size1, stride=1, padding=2),
            nn.ReLU(),
            # nn.MaxPool2d(5, stride=3, padding=2),
            nn.Upsample(scale_factor=2),

            nn.Conv2d(n_out_channels2, n_out_channels1, kernel_size2, stride=1, padding=2),
            nn.ReLU(),
            nn.Upsample(scale_factor=2),

            nn.Conv2d(n_out_channels1, N_IN_CHANNELS, kernel_size3, stride=1, padding=2),
            nn.Upsample(scale_factor=2),
            nn.ReLU(),
        )

    def forward(self, x):
        x = self.encoder(x)
        x = self.decoder(x)
        return x

    def encode(self, x):
        return self.encoder(x)

class FaceAutoencoder(nn.Module):
    def __init__(self, n_out_channels1=4, n_out_channels2=4, n_out_channels3=1, \
                kernel_size1=5, kernel_size2=5, kernel_size3=5):
        super(FaceAutoencoder, self).__init__()
        self.encoder = nn.Sequential(
            nn.Conv2d(N_IN_CHANNELS, out_channels=n_out_channels1, kernel_size=kernel_size1, stride=2, padding=2), # [3,160,160] -> [4, 80, 80]
            nn.ReLU(),

            nn.Dropout(0.3),

            nn.Conv2d(in_channels=n_out_channels1, out_channels=n_out_channels2, kernel_size=kernel_size2, stride=2, padding=2), # [3,80,80] -> [4, 40, 40]
            nn.ReLU(),
            nn.MaxPool2d(3, stride=1, padding=0), # [4, 40, 40] -> [4, 38, 38]

            nn.Dropout(0.3),

            nn.Conv2d(in_channels=n_out_channels2, out_channels=n_out_channels3, kernel_size=kernel_size3, stride=1, padding=1), # [4, 36, 36] -> [1, 36, 36]
            nn.MaxPool2d(5, stride=1, padding=2),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.Conv2d(n_out_channels3, n_out_channels2, kernel_size1, stride=1, padding=2), # [1, 36, 36] -> [4, 36, 36]
            nn.ReLU(),
            # nn.MaxPool2d(5, stride=3, padding=2),
            nn.Upsample(size=(40, 40)),

            nn.Dropout(0.3),

            nn.Conv2d(n_out_channels2, n_out_channels1, kernel_size2, stride=1, padding=2),
            nn.ReLU(),
            nn.Upsample(scale_factor=2),

            nn.Dropout(0.3),

            nn.Conv2d(n_out_channels1, N_IN_CHANNELS, kernel_size3, stride=1, padding=2),
            nn.ReLU(),
            nn.Upsample(scale_factor=2),
        )

    def forward(self, x):
        x = self.encoder(x)
        x = self.decoder(x)
        return x

    def encode(self, x):
        return self.encoder(x)


# copied from 
# https://github.com/pytorch/examples/tree/master/word_language_model
class PositionalEncoding(nn.Module):
    def __init__(self, d_model, dropout=0.1, max_len=5000):
        super(PositionalEncoding, self).__init__()
        self.dropout = nn.Dropout(p=dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0).transpose(0, 1)
        self.register_buffer('pe', pe)

    def forward(self, x):
        x = x + self.pe[:x.size(0), :]
        return self.dropout(x)

class Classifier(nn.Module):
    def __init__(self, n_vid_features, n_aud_features, n_head, n_layers, dim_feedforward, n_linear_hidden=30, dropout=0.3):
        super(Classifier, self).__init__()
        vid_encoder_layer = nn.TransformerEncoderLayer(d_model=n_vid_features, nhead=n_head, dim_feedforward=dim_feedforward)
        self.vid_transformer_encoder = nn.TransformerEncoder(vid_encoder_layer, num_layers=n_layers)
        self.vid_classifier = nn.Linear(n_vid_features, 1)
        aud_encoder_layer = nn.TransformerEncoderLayer(d_model=n_aud_features, nhead=1, dim_feedforward=dim_feedforward)
        self.aud_transformer_encoder = nn.TransformerEncoder(aud_encoder_layer, num_layers=n_layers)
        self.output = nn.Linear(2, 1)

    def forward(self, vid, aud):
        vid = self.vid_transformer_encoder(vid)
        vid = self.vid_classifier(vid)
        vid = torch.sigmoid(vid)
        vid = torch.max(vid, axis=0)[0]
        aud = self.aud_transformer_encoder(aud)
        aud = torch.sigmoid(aud)
        aud = torch.max(aud, axis=0)[0]
        x = torch.cat((vid, aud), axis=1)
        x = self.output(x)
        return x

class FaceClassifier(nn.Module):
    def __init__(self, n_linear_hidden=256, lstm_hidden_dim=128, num_lstm_layers=1, dropout=0.1):
        super(FaceClassifier, self).__init__()

        # Завантаження попередньо натренованої EfficientNet
        self.cnn = models.efficientnet_b7(pretrained=True)
        self.feature_extractor = nn.Sequential(*list(self.cnn.children())[:-1])  # Виключаємо шар класифікації

        # Розмір виходу від feature extractor
        self.feature_output_size = 2560  # EfficientNet B7 дає 2560 ознак

        # LSTM для обробки послідовності ознак кожного кадру
        self.lstm = nn.LSTM(input_size=self.feature_output_size, 
                            hidden_size=lstm_hidden_dim, 
                            num_layers=num_lstm_layers, 
                            batch_first=True, 
                            bidirectional=True)
        
        # Повнозв'язні шари для класифікації
        self.fc1 = nn.Linear(2 * lstm_hidden_dim, n_linear_hidden)  # множимо на 2 через bidirectional LSTM
        self.fc2 = nn.Linear(n_linear_hidden, 1)

    def forward(self, vid_frames):
        # Витягання ознак для кожного кадру
        batch_size, num_frames, channels, height, width = vid_frames.shape
        vid_frames = vid_frames.view(batch_size * num_frames, channels, height, width)

        # Використовуємо фічерний екстрактор
        with torch.no_grad():
            vid_features = self.feature_extractor(vid_frames)

        # Переформатовуємо ознаки для LSTM
        vid_features = vid_features.view(batch_size, num_frames, -1)  # (batch_size, num_frames, feature_output_size)

        # Обробка послідовності кадрів через LSTM
        lstm_out, _ = self.lstm(vid_features)  # lstm_out: (batch_size, num_frames, 2 * lstm_hidden_dim)

        # Використання середнього значення по кадрам для об'єднання послідовності (можна також використовувати останній кадр або інші методи агрегації)
        lstm_out = torch.mean(lstm_out, dim=1)  # (batch_size, 2 * lstm_hidden_dim)

        # Класифікаційні шари
        x = torch.relu(self.fc1(lstm_out))
        x = self.fc2(x)

        return x

class LstmAutoencoder(nn.Module):
    def __init__(self, device, batch_size, seq_length, lstm_size):
        super(LstmAutoencoder, self).__init__()
        self.device = device
        self.batch_size = batch_size
        self.seq_length = seq_length
        self.lstm_size = lstm_size

        self.encoder = nn.LSTM(input_size=1, hidden_size=lstm_size, num_layers=2, dropout=0.3)
        # self.dropout = nn.Dropout(dropout)
        self.decoder = nn.LSTM(input_size=1, hidden_size=lstm_size, num_layers=2, dropout=0.3)
        self.linear = nn.Linear(lstm_size, 1)
        self.softmax = nn.Softmax(dim=2)

    def forward(self, x):
        _, last_state = self.encoder(x)
        outs_total = torch.zeros(self.seq_length, self.batch_size, 1, device=self.device)
        decoder_input = torch.zeros(1, self.batch_size, 1, device=self.device)
        for i in range(self.seq_length):
            outs, last_state = self.decoder(decoder_input, last_state)
            outs = self.linear(outs)
            outs = self.softmax(outs)
            outs_total[i,...] = outs
        return outs_total
