from app import app
from flask import render_template, redirect, url_for
import json
import requests
from bs4 import BeautifulSoup
import os
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt

def extract_element(ancestor, selector, attribute=None, extract_list=False):
    try:
        if extract_list:
            return ", ".join([item.text.strip() for item in ancestor.select(selector)])
        if attribute:
            return ancestor.select(selector).pop(0)[attribute].strip()
        return ancestor.select(selector).pop(0).text.strip()
    except IndexError: return None

selectors = {
    "author": ["span.user-post__author-name"],
    "recommendation": ["span.user-post__author-recomendation > em"],
    "stars": ["span.user-post__score-count"],
    "content": ["div.user-post__text"],
    "publish_date": ["span.user-post__published > time:nth-child(1)", "datetime"], 
    "purchase_date": ["span.user-post__published > time:nth-child(2)", "datetime"],
    "useful": ["span[id^=votes-yes]"],
    "useless": ["span[id^=votes-no]"],
    "pros": ["div.review-feature__title--positives ~ div.review-feature__item", None, True],
    "cons": ["div.review-feature__title--negatives ~ div.review-feature__item", None, True]
}

@app.route('/')
def index():
    return render_template("index.html.jinja")

@app.route('/author')
def author():
    return render_template("author.html.jinja")

@app.route('/extract/<product_id>')
def  extract(product_id):
    url_pre = "https://www.ceneo.pl/"
    url_post = "/opinie-"
    page_no = 1
    all_reviews = []

    while(page_no):
        url = url_pre+product_id+url_post+str(page_no)
        response = requests.get(url, allow_redirects=False)
        if response.status_code == requests.codes.ok: 
            page_dom = BeautifulSoup(response.text, 'html.parser')
            reviews = page_dom.select("div.js_product-review")
            for review in reviews: 
                single_review = {
                    key: extract_element(review, *value)
                        for key, value in selectors.items()
                }

                single_review["review_id"] = review["data-entry-id"]
                single_review["recommendation"] = True if single_review["recommendation"] == "Polecam" else False if single_review["recommendation"] == "Nie polecam" else None
                single_review["stars"] = float(single_review["stars"].split("/").pop(0).replace(",", "."))
                single_review["content"] = single_review["content"].replace("\n", " ").replace("  ", " ").strip()
                single_review["publish_date"] = single_review["publish_date"].split(" ").pop(0)
                try:
                    single_review["purchase_date"] = single_review["purchase_date"].split(" ").pop(0)
                except AttributeError:
                    single_review["purchase_date"] = None
                single_review["useful"] = int(single_review["useful"])
                single_review["useless"] = int(single_review["useless"])

                all_reviews.append(single_review)
            page_no += 1
        else: page_no = None

    if not os.path.exists("app/reviews"):
        os.makedirs("app/reviews")
    f = open("app/reviews/"+product_id+".json", "w", encoding="UTF-8")
    json.dump(all_reviews, f, indent=4, ensure_ascii=False)
    return redirect(url_for('product', product_id=product_id))

@app.route('/products')
def  products():
    if not os.path.exists("app/reviews"):
        os.makedirs("app/reviews")
    products = [filename.split(".")[0] for filename in os.listdir("app/reviews")]
    return render_template("products.html.jinja", products=products)

@app.route('/product/<product_id>')
def  product(product_id):
    opinions = pd.read_json("app/reviews/"+product_id+".json")
    stats = {
        "opinions_count": len(opinions),
        "pros_count": opinions["pros"].astype(bool).sum(),
        "cons_count": opinions["cons"].astype(bool).sum(),
        "average_score": opinions["stars"].mean().round(2)
    }
    if not os.path.exists("app/plots"):
        os.makedirs("app/plots")
    recommendations = opinions["recommendation"].value_counts(dropna=False).sort_index().reindex([False, True, None], fill_value=0)
    recommendations.plot.pie(
        autopct = "%.1f%%",
        label = "",
        title = "Rekomendacje",
        labels = ["Nie polecam", "Polecam", "Nie mam zdania"],
        colors = ["crimson", "forestgreen", "lightskyblue"]
    )
    plt.savefig("app/plots/"+product_id+"_recommendations.png")
    plt.close()
    stars = opinions["stars"].value_counts(dropna=False).sort_index().reindex(np.arange(0,5.5,0.5), fill_value=0)
    stars.plot.bar(
        title = "Oceny"
    )
    plt.savefig("app/plots/"+product_id+"_stars.png")
    plt.close()
    return render_template("product.html.jinja", product_id=product_id, stats=stats, opinions=opinions)
