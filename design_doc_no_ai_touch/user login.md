1. a user should enter all his/her information before he can start. if some field is missing, showing a message to remind 
the user fill in that field. 

2. when a user enter all his/her information, we check
    a. if the user name has been used bofore. 
        - if no, we let the user begin his/her session. 
        - if yes, we check if the user's age, gender, education information is exactly the same as before. 
            i. if yes, we assume the user is the same user, and let him/her resume his session. 
            ii. if not exactly the same, we ask the user to enter another user name because this one is already being used before. 
    b. if a user has reach limit (by default 10), we ask if he/her still wants to do more. if he/she wants to do more, then we increase his/her limit by 5, and let the user enter session. 