  # Start from a Python image                                                                         
  FROM python:3.13-slim                                                                               
  
  # Install uv                                                                                        
  COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv                                     
                                                                                                      
  # Copy your project files into the container
  WORKDIR /app                                                                                        
  COPY . .                                                                                          
                                                                                                      
  # Install dependencies
  RUN uv sync                                                                                         
                                                                                                    
  # Tell the container to expose port 8000
  EXPOSE 8000

  # Run your server                                                                                   
  CMD ["uv", "run", "valorant-mcp"]