from app import application

if __name__ == '__main__':
    print("""
                                            
    _/    _/        _/_/_/     _/_/_/_/_/   
   _/  _/        _/                   _/    
  _/_/          _/                 _/       
 _/  _/        _/               _/          
_/    _/        _/_/_/       _/             
                                            
    """)
    print("=============================")
    print("""A Cybersecurity Game""")
    print("=============================")
    print("""If you just want to play
See: https://kc7cyber.com \n
If you want to make your own data
    See: https://github.com/kkneomis/kc7/\n
For training Materials:
    See: https://kc7cyber.com/modules
    """)

    print("""
To get started go to http://127.0.0.1:8889/login
Login username:password -> admin:DefNotAdmin 
    """)
    application.run(debug=True, port="8889")

