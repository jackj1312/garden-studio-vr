// Public EA LiDAR + current registered capture. Evidence and limits:
// assets/sites/house-wip/survey/frontage_v1.json. Metres in the viewer's frame.
export const frontageSurvey=Object.freeze({
 revision:'2026-11-06-lidar-video-1',start:21.6900003,wall:23.048814535,
 grassIntercept:27.3403211621,grassSlope:.0490770671,
 kerbIntercept:28.5614311765,kerbSlope:-.0019827688,
 crossfallX:-.0294889519,crossfallZ:-.0239907756,
 referenceX:9.13,ground:-.2390000075,paving:-.2310000062,
 kerbWidth:.15,kerbRise:.08,roadWidth:8.2,
});
export const kerbEdge=x=>frontageSurvey.kerbIntercept+frontageSurvey.kerbSlope*(x-4.63);
export function grassEdge(x){
 const bounded=Math.max(-9.37,Math.min(11.82,x));
 return frontageSurvey.grassIntercept+frontageSurvey.grassSlope*(bounded-4.63)+kerbEdge(x)-kerbEdge(bounded);
}
const clamp=t=>Math.max(0,Math.min(1,t));
export function frontageLevel(x,z,kind='verge'){
 const s=frontageSurvey,g=grassEdge(x),k=kerbEdge(x);
 const across=s.crossfallX*(x-s.referenceX);
 // Retained thresholds govern the local datum. The current scan gives a 70 mm
 // fall to grass/path contact; LiDAR supplies the broad fall along the street.
 const t=clamp((z-s.wall)/(g-s.wall));
 const pathY=s.ground-.070+across;
 if(kind==='road')return pathY-.010-s.kerbRise+s.crossfallZ*(z-k-s.kerbWidth);
 if(kind==='kerb')return pathY-.010;
 if(z>=g)return pathY-.010*clamp((z-g)/(k-g));
 return s.ground-.070*t+across*t;
}
