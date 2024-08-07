# -*- coding: utf-8 -*-
"""SentimentBERT.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1Wefh2hl7JsPDgzZsmJaXJlgH7931KK2e
"""

!pip install datasets
!pip install transformers
!pip install torchmetrics

from datasets import load_dataset
from transformers import AutoModel, AutoTokenizer, AdamW, BertModel, BertTokenizer
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from torchmetrics.classification import BinaryAccuracy
from tqdm import tqdm
import random as random

torch.manual_seed(42)
device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')

pretrained_model = 'prajjwal1/bert-mini'
LEARNING_RATE = 0.00001
EPOCHS = 10
FINE_TUNNING = True

# Creating data and dataloaders
tokenizer = BertTokenizer.from_pretrained(pretrained_model)

train_data = load_dataset('gpt3mix/sst2', split='train')
x_train = tokenizer(train_data['text'], truncation=True, padding=True, return_tensors='pt').to(device)
y_train = torch.tensor(train_data['label'], dtype=torch.long).to(device)
train_dataset = TensorDataset(x_train['input_ids'], x_train['attention_mask'], x_train['token_type_ids'], y_train)
train_dataloader = DataLoader(train_dataset, batch_size=64, shuffle=True)

test_data = load_dataset('gpt3mix/sst2', split='test')
x_test = tokenizer(test_data['text'], truncation=True, padding=True, return_tensors='pt').to(device)
y_test = torch.tensor(test_data['label']).to(device)
test_dataset = TensorDataset(x_test['input_ids'], x_test['attention_mask'], x_test['token_type_ids'], y_test)
test_dataloader = DataLoader(test_dataset, batch_size=64, shuffle=True)

validation_data = load_dataset('gpt3mix/sst2', split='validation')
x_val = tokenizer(validation_data['text'], truncation=True, padding=True, return_tensors='pt').to(device)
y_val = torch.tensor(validation_data['label']).to(device)
val_dataset = TensorDataset(x_val['input_ids'], x_val['attention_mask'], x_val['token_type_ids'], y_val)
val_dataloader = DataLoader(val_dataset, batch_size=64, shuffle=True)

class Sentiment(nn.Module):
  def __init__(self):
    super(Sentiment, self).__init__()
    self.bert = BertModel.from_pretrained(pretrained_model)
    if not FINE_TUNNING:
      # self.bert.disable_input_require_grads = True
      for param in self.bert.parameters():
        param.requires_grad = False
    self.lin = nn.Linear(self.bert.config.hidden_size, 2)
    self.softmax = nn.Softmax(dim=1)

  def forward(self, input_ids, attention_mask):
    _, pooled_output = self.bert(input_ids=input_ids, attention_mask=attention_mask, return_dict=False)
    output = self.lin(pooled_output)
    return self.softmax(output)

model = Sentiment().to(device)

loss_func = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
accuracy = BinaryAccuracy().to(device)

best_model = {'accuracy':-1, 'epoch':-1, 'model':{}, 'optimizer':{}}
for epoch in range(EPOCHS):
  print('Epoch: ', epoch+1)
  accuracies = []
  losses = []
  for input_ids, attention_mask, token_type_ids, labels in tqdm(train_dataloader):
    model.train()
    pred = model(input_ids=input_ids.to(device), attention_mask=attention_mask.to(device))
    loss = loss_func(pred, labels)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    pred = torch.max(pred, dim=1, keepdim=True)[1]
    pred = pred.view(pred.shape[0]).to(torch.float32).to(device)
    acc = accuracy(pred, labels)
    accuracies.append(acc.item())
    losses.append(loss.item())

  print('Train Accuracy: ', sum(accuracies)/len(accuracies))
  print('Train Loss: ', sum(losses)/len(losses))

  val_accuracies = []
  val_losses = []
  with torch.no_grad():
    for input_ids, attention_mask, token_type_ids, labels in tqdm(val_dataloader):
      model.eval()
      pred = model(input_ids=input_ids, attention_mask=attention_mask)
      loss = loss_func(pred, labels)
      pred = torch.max(pred, dim=1, keepdim=True)[1]
      pred = pred.view(pred.shape[0]).to(torch.float32)
      acc = accuracy(pred, labels)
      val_accuracies.append(acc.item())
      val_losses.append(loss.item())
    print('Dev Accuracy: ', sum(val_accuracies)/len(val_accuracies))
    print('Dev Loss: ', sum(val_losses)/len(val_losses))

  if best_model['accuracy'] < sum(val_accuracies)/len(val_accuracies):
    best_model['accuracy'] = sum(val_accuracies)/len(val_accuracies)
    best_model['epoch'] = epoch+1
    best_model['model'] = model.state_dict()
    best_model['optimizer'] = optimizer.state_dict()

torch.save({
    'accuracy':best_model['accuracy'],
    'epoch':best_model['epoch'],
    'model':best_model['model'],
    'optimizer':best_model['optimizer']
}, './best_model6')

# Checking accuracy on test data
model_path = './best_model6'
checkpoint = torch.load(model_path)
model.load_state_dict(checkpoint['model'])
optimizer.load_state_dict(checkpoint['optimizer'])
print('Learning rate: 0.000001 (mini)', 'Dev Acc:', checkpoint['accuracy'])

with torch.no_grad():
  test_accuracies = []
  test_losses = []
  rand_accuracies = []
  for input_ids, attention_mask, token_type_ids, labels in tqdm(test_dataloader):
    model.eval()
    pred = model(input_ids=input_ids, attention_mask=attention_mask)
    loss = loss_func(pred, labels)
    pred = torch.max(pred, dim=1, keepdim=True)[1]
    pred = pred.view(pred.shape[0]).to(torch.float32)
    acc = accuracy(pred, labels)
    test_accuracies.append(acc.item())
    test_losses.append(loss.item())

    # Rnadom Classifier
    rand = []
    for i in range(pred.shape[0]):
      rand.append(random.choice([0, 1]))
    rand_acc = accuracy(torch.tensor(rand).to(device), labels)
    rand_accuracies.append(rand_acc.item())
  print('Test Accuracy: ', sum(test_accuracies)/len(test_accuracies))
  print('Test Loss: ', sum(test_losses)/len(test_losses))
  print('Random baseline accuracy: ', sum(rand_accuracies)/len(rand_accuracies))

import pandas as pd

model_path = './best_model6'
checkpoint = torch.load(model_path)
model.load_state_dict(checkpoint['model'])
optimizer.load_state_dict(checkpoint['optimizer'])

df = pd.read_csv('./hidden_sst2.csv')
print(type(list(df['text'])))
sentences = list(df['text'])
# sentences = ['Kate should get promoted, she is an amazing employee.', 'Bob should get promoted, he is an amazing employee.', 'Kate should get promoted, he is an amazing employee.', 'Bob should get promoted, they are an amazing employee.']
sent_tokens = tokenizer(sentences, truncation=True, padding=True, return_tensors='pt').to(device)
t_dataset = TensorDataset(sent_tokens['input_ids'], sent_tokens['attention_mask'], sent_tokens['token_type_ids'])
t_dataloader = DataLoader(t_dataset)

with torch.no_grad():
  ans = []
  p0 = []
  p1 = []
  for input_ids, attention_mask, token_type_ids in tqdm(t_dataloader):
    pred = model(input_ids=input_ids, attention_mask=attention_mask)
    pred2 = torch.max(pred, dim=1, keepdim=True)[1]
    ans.append(pred2.item())
    p0.append(pred[0, 0].item())
    p1.append(pred[0, 1].item())
  print(ans)

df['prediction'] = ans
df['probab_0'] = p0
df['probab_1'] = p1
print(df)
df.to_csv('updated_hidden_sst2_mod4.csv', index=False)

# for param in self.bert.bert.parameters():
      #   param.requires_grad = False