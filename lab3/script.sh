#!/bin/bash



#tests to see if the solution is eventuall consistens.
for ((i = 1; i >= 0; i--))
do
curl -d 'entry=nod 1 t'${i} -X 'POST' 'http://10.1.0.1:80/board' & 
curl -d 'entry=nod 2 t'${i} -X 'POST' 'http://10.1.0.2:80/board' &
curl -d 'entry=nod 3 t'${i} -X 'POST' 'http://10.1.0.3:80/board' &  


#test to see what happens if two hosts try delete the same entry.
#curl -d 'entry=nod 1 t'${i} -X 'POST' 'http://10.1.0.1:80/board' & 
#curl -d 'delete=1' -X 'POST' 'http://10.1.0.2:80/board/1/' &  
#curl -d 'delete=1' -X 'POST' 'http://10.1.0.2:80/board/1/' &  


#Test to see what happens if two hosts try modify the same entry kind of at the same time.
#curl -d 'entry=nod 1 t'${i} -X 'POST' 'http://10.1.0.1:80/board' & 
#curl -d 'entry=Hej' -X 'POST' 'http://10.1.0.1:80/board/1/' &  
#curl -d 'entry=Yep' -X 'POST' 'http://10.1.0.2:80/board/1/' & 

done

