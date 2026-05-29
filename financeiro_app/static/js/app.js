function parseData(el, attr){try{return JSON.parse(el.dataset[attr]||"[]")}catch(e){return []}}

document.addEventListener("DOMContentLoaded",()=>{
  const category=document.getElementById("categoryChart");
  if(category){
    new Chart(category,{type:"doughnut",data:{labels:parseData(category,"labels"),datasets:[{data:parseData(category,"values")}]},options:{responsive:true,plugins:{legend:{position:"bottom"}}}});
  }
  const month=document.getElementById("monthChart");
  if(month){
    new Chart(month,{type:"bar",data:{labels:parseData(month,"months"),datasets:[{label:"Receitas",data:parseData(month,"income")},{label:"Despesas",data:parseData(month,"expense")}]},options:{responsive:true,plugins:{legend:{position:"bottom"}},scales:{y:{beginAtZero:true}}}});
  }
});
