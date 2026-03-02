# Data Cleaning Agent

## Setup
```bash
- python 3.14
```

> Note: I had to change the following since the new langchain version changed the import path.

```python
       8 -from langchain.prompts import PromptTemplate                   
       8 +from langchain_core.prompts import PromptTemplate    
```

## Understanding the code
As I didn't really understand the code, I decided to create a simple notebook that goes step by step through the code.

See `test.ipynb` for more details.

## Improvements

1. Add outlier summary in the dataframe summary function