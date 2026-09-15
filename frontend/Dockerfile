FROM node:20-slim

WORKDIR /app

COPY package.json ./
RUN npm install --no-audit --no-fund

COPY . .

ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

EXPOSE 3000

CMD ["npm", "run", "dev"]
